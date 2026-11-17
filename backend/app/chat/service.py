"""Lógica de negocio del Conversational Agent Service: inferencia asíncrona.

Flujo (Req 3.1, 3.5-3.9, 12.4):
1. `encolar_mensaje_texto` valida el texto (Tarea 11.1), lo redacta (Tarea 11.2)
   y persiste la interacción en estado "encolado"; responde de inmediato (202).
2. `procesar_inferencia` ejecuta la inferencia del modelo a través del circuit
   breaker (Req 11.5, 11.6) con timeout de 60 s (Req 3.8); al modelo solo llega
   texto ya redactado (Req 3.10). Al terminar deja la interacción en "listo" o,
   ante fallo/timeout, en "error" conservando el historial (Req 3.8).
3. `obtener_resultado` y `obtener_historial` consultan ancladas al Usuario
   autenticado (anti-BOLA): un Usuario nunca ve interacciones de otro.

Usa el ORM con consultas parametrizadas y no registra PII (el contenido se
persiste ya redactado). El texto de voz (STT) y el TTS llegan en la Tarea 11.4.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import audit, guardrails
from app.chat.constants import (
    CANAL_VOZ,
    ESTADO_ENCOLADO,
    ESTADO_ERROR,
    ESTADO_LISTO,
    ESTADO_PROCESANDO,
    ESTADO_REPETIR_VOZ,
    GUARDRAIL_BLOQUEO_ENTRADA,
    GUARDRAIL_DERIVADO,
    GUARDRAIL_KILL_SWITCH,
    GUARDRAIL_PERMITIDO,
    GUARDRAIL_SALIDA_NO_VALIDADA,
    INFERENCE_TIMEOUT_SECONDS,
    PROCESSING_INDICATOR_SECONDS,
    SAFE_FALLBACK_RESPONSE,
    STT_CONFIDENCE_THRESHOLD,
)
from app.chat.dto import (
    ChatHistory,
    ChatHistoryItem,
    ChatMessageAccepted,
    ChatMessageResult,
    ChatTextMessageIn,
)
from app.chat.inference import (
    GenerativeModel,
    NoopTts,
    SpeechToText,
    TextToSpeech,
)
from app.chat.errors import RedaccionPiiError
from app.chat.models import AiInteraction
from app.chat.proveedores import obtener_modelo, obtener_stt
from app.chat.prompt import ETIQUETAS_ACTIVIDAD, construir_prompt, contexto_del_perfil
from app.chat.redaction import redactar_pii
from app.chat.validation import validar_mensaje_texto, validar_nota_de_voz
from app.common.config import get_settings
from app.common.correlation import get_correlation_id
from app.common.errors import NotFoundError
from app.common.logging import log_event
from app.common.resilience import CircuitBreaker
from app.conversion.catalog import nombres_de_ofertas, nombres_de_todas_las_ofertas
from app.profile.models import Profile

logger = logging.getLogger("cima.chat")

CANAL_TEXTO = "texto"

# Circuit breakers por dependencia externa (Req 11.5).
_llm_breaker = CircuitBreaker("llm")
_stt_breaker = CircuitBreaker("stt")


async def encolar_mensaje_texto(
    db: AsyncSession, current_user_id: uuid.UUID, data: ChatTextMessageIn
) -> ChatMessageAccepted:
    """Valida, redacta y encola un mensaje de texto; responde 202 (Req 3.1, 3.5).

    El texto se valida (1-2000 chars tras trim) y se redacta la PII ANTES de
    persistir y de cualquier invocación al modelo (Req 3.2, 3.10). La interacción
    queda en estado "encolado" asociada al Usuario autenticado.

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado (titular de la interacción).
        data: mensaje de texto validado por el DTO (allowlist de campos).

    Returns:
        El acuse con el id de la interacción y cuándo mostrar el indicador.
    """
    normalizado = validar_mensaje_texto(data.text)
    redactado = redactar_pii(normalizado)

    interaccion = AiInteraction(
        profile_id=current_user_id,
        input_redacted=redactado.texto,
        input_channel=CANAL_TEXTO,
        status=ESTADO_ENCOLADO,
        correlation_id=get_correlation_id(),
    )
    db.add(interaccion)
    await db.commit()
    await db.refresh(interaccion)
    log_event(
        logger,
        "chat_message_enqueued",
        interaction_id=str(interaccion.id),
        channel=CANAL_TEXTO,
        pii_categorias=redactado.categorias,
    )
    return ChatMessageAccepted(
        id=interaccion.id,
        status=interaccion.status,
        processing_after_seconds=PROCESSING_INDICATOR_SECONDS,
    )


async def encolar_nota_de_voz(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    audio: bytes,
    duracion_segundos: float,
    stt: SpeechToText | None = None,
) -> ChatMessageAccepted:
    """Valida, transcribe y encola una Nota de Voz; responde 202 (Req 14.2, 14.5, 14.6).

    Flujo voz-first:
    1. Valida el audio (formato real y duración, Tarea 11.1) sin invocar STT si
       no cumple.
    2. Transcribe con STT a través del circuit breaker; si falla, el estado queda
       en "repetir_voz" (no se culpa al Usuario, Req 14.5).
    3. Si la confianza del STT es baja o el texto queda vacío, se pide repetir
       (estado "repetir_voz") sin invocar el modelo (Req 14.5).
    4. Redacta la PII de la transcripción ANTES de persistir y de encolar la
       inferencia (Req 14.6). El audio NO se persiste: solo se usó para transcribir.

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado (titular de la interacción).
        audio: binario de la Nota de Voz.
        duracion_segundos: duración medida en el servidor.
        stt: transcriptor a usar; por defecto, el de respaldo que pide repetir.

    Returns:
        El acuse con el id y el estado ("encolado" o "repetir_voz").
    """
    nota = validar_nota_de_voz(audio, duracion_segundos)
    stt = stt or obtener_stt()

    async def _transcribir() -> object:
        return await stt.transcribe(audio, nota.formato)

    try:
        transcripcion = await _stt_breaker.llamar(
            _transcribir, timeout=float(INFERENCE_TIMEOUT_SECONDS)
        )
    except Exception:
        # Fallo del STT: se pide repetir sin culpar al Usuario (Req 14.5). El
        # audio no se conserva (Req 14.6) y no se invoca el modelo.
        log_event(logger, "chat_stt_failed", channel=CANAL_VOZ)
        return await _encolar_repeticion_voz(db, current_user_id)

    texto = transcripcion.text.strip()
    if transcripcion.confidence < STT_CONFIDENCE_THRESHOLD or not texto:
        # Confianza insuficiente o transcripción vacía: pedir repetición (Req 14.5).
        log_event(
            logger,
            "chat_stt_low_confidence",
            channel=CANAL_VOZ,
            confidence=round(transcripcion.confidence, 2),
        )
        return await _encolar_repeticion_voz(db, current_user_id)

    # Redacción de PII sobre la transcripción antes de persistir/modelo (Req 14.6).
    redactado = redactar_pii(texto)
    interaccion = AiInteraction(
        profile_id=current_user_id,
        input_redacted=redactado.texto,
        input_channel=CANAL_VOZ,
        status=ESTADO_ENCOLADO,
        correlation_id=get_correlation_id(),
    )
    db.add(interaccion)
    await db.commit()
    await db.refresh(interaccion)
    log_event(
        logger,
        "chat_voice_enqueued",
        interaction_id=str(interaccion.id),
        channel=CANAL_VOZ,
        pii_categorias=redactado.categorias,
    )
    return ChatMessageAccepted(
        id=interaccion.id,
        status=interaccion.status,
        processing_after_seconds=PROCESSING_INDICATOR_SECONDS,
        # Lo que se entendió, ya redactado: el cliente lo muestra para que el
        # Usuario vea si coincide con lo que dijo.
        input_redacted=interaccion.input_redacted,
    )


async def _encolar_repeticion_voz(
    db: AsyncSession, current_user_id: uuid.UUID
) -> ChatMessageAccepted:
    """Registra una interacción de voz que requiere repetición (Req 14.5).

    No persiste contenido del Usuario (la transcripción no fue confiable y el
    audio no se conserva). Devuelve el estado "repetir_voz" para que el cliente
    pida repetir en lenguaje simple.

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado.

    Returns:
        El acuse con estado "repetir_voz".
    """
    interaccion = AiInteraction(
        profile_id=current_user_id,
        input_redacted="",
        input_channel=CANAL_VOZ,
        status=ESTADO_REPETIR_VOZ,
        correlation_id=get_correlation_id(),
    )
    db.add(interaccion)
    await db.commit()
    await db.refresh(interaccion)
    return ChatMessageAccepted(
        id=interaccion.id,
        status=interaccion.status,
        processing_after_seconds=PROCESSING_INDICATOR_SECONDS,
    )


async def procesar_inferencia(
    db: AsyncSession,
    interaction_id: uuid.UUID,
    modelo: GenerativeModel | None = None,
    tts: TextToSpeech | None = None,
) -> None:
    """Procesa una inferencia encolada contra el modelo, con circuit breaker.

    Marca la interacción "procesando", invoca al modelo a través del circuit
    breaker con timeout de 60 s (Req 3.8, 11.5) pasándole solo texto redactado
    (Req 3.10), y la deja en "listo" con la respuesta o en "error" si falla o se
    agota el tiempo, conservando el historial (Req 3.8).

    Esta función la ejecuta el worker asíncrono. Se expone por separado del
    endpoint para poder encolarla en una cola real sin cambiar el contrato.

    Args:
        db: sesión de base de datos.
        interaction_id: interacción a procesar.
        modelo: modelo de IA a usar; por defecto, el que indica la
            configuración (`obtener_modelo`), que cae al respaldo seguro si el
            proveedor no puede usarse.
    """
    modelo = modelo or obtener_modelo()
    tts = tts or NoopTts()
    interaccion = await db.get(AiInteraction, interaction_id)
    if interaccion is None:
        raise NotFoundError(internal_detail="interaction not found for inference")
    if interaccion.status != ESTADO_ENCOLADO:
        # Idempotencia: una interacción ya procesada o en curso no se reprocesa.
        return

    interaccion.status = ESTADO_PROCESANDO
    await db.commit()

    texto_redactado = interaccion.input_redacted

    # Kill switch (Req 16.6): si el agente está degradado, se responde con el
    # mensaje de respaldo seguro sin invocar el modelo.
    if not get_settings().chat_agent_enabled:
        await _finalizar_con_respaldo(db, interaccion, tts, GUARDRAIL_KILL_SWITCH)
        return

    # Guardrail de entrada (Req 16.1): bloquea contenido inseguro/fuera de dominio
    # antes de invocar el modelo.
    if guardrails.evaluar_entrada(texto_redactado) != GUARDRAIL_PERMITIDO:
        await _finalizar_con_respaldo(db, interaccion, tts, GUARDRAIL_BLOQUEO_ENTRADA)
        return

    # Prompt con roles separados (Tarea 11.4, OWASP LLM01): el texto del Usuario
    # va solo en el mensaje `user`. Se arma FUERA del circuit breaker: si se
    # rechaza (PII residual, Req 3.11), es un problema del contenido y no del
    # proveedor, y no debe contar para abrir el circuito de todos los Usuarios.
    # El Perfil se lee una sola vez, del `profile_id` guardado en el servidor
    # (anti-BOLA): sirve para el contexto del prompt y para validar ofertas.
    perfil = await db.get(Profile, interaccion.profile_id)
    contexto = _contexto_del_usuario(perfil, interaccion)
    try:
        prompt = construir_prompt(texto_redactado, contexto=contexto)
    except RedaccionPiiError:
        log_event(logger, "chat_prompt_rechazado", interaction_id=str(interaccion.id))
        interaccion.status = ESTADO_ERROR
        await db.commit()
        audit.registrar_auditoria(interaccion)
        return

    async def _invocar() -> object:
        return await modelo.generate(prompt)

    try:
        resultado = await _llm_breaker.llamar(
            _invocar, timeout=float(INFERENCE_TIMEOUT_SECONDS)
        )
    except Exception:
        # El worker no debe caer por un fallo del modelo: cualquier error o
        # timeout (ya envuelto por el circuit breaker) deja la interacción en
        # "error" conservando el historial (Req 3.8). El detalle se registra sin
        # PII; no se silencia, se traduce a un estado observable por el cliente.
        interaccion.status = ESTADO_ERROR
        await db.commit()
        audit.registrar_auditoria(interaccion)
        return

    # Validación de salida y derivación (Req 16.2, 16.3). Las ofertas solo se
    # permiten si están respaldadas por el catálogo del Usuario (Req 5.4).
    decision = _evaluar_salida(perfil, resultado.text)
    if decision != GUARDRAIL_PERMITIDO:
        await _finalizar_con_respaldo(db, interaccion, tts, decision, resultado.model_version)
        return

    interaccion.response_text = guardrails.marcar_como_ia(resultado.text)
    interaccion.model_version = resultado.model_version
    interaccion.guardrail_decision = GUARDRAIL_PERMITIDO
    interaccion.response_audio_ref = await _sintetizar_respuesta(
        tts, interaccion.response_text
    )
    interaccion.status = ESTADO_LISTO
    await db.commit()
    audit.registrar_auditoria(interaccion)


def _contexto_del_usuario(perfil: Profile | None, interaccion: AiInteraction) -> str | None:
    """Arma el contexto del Perfil para el modelo (Req 4.8, 6.7), sin PII.

    `perfil` es el del `profile_id` de la interacción guardada en el servidor,
    nunca un dato del cliente (anti-BOLA). Solo usa el tipo de actividad y la
    zona; el teléfono no sale de aquí. Si no hay Perfil, el prompt sale sin
    contexto. El registro solo indica qué campos se incluyeron, no sus valores.
    """
    if perfil is None:
        return None
    contexto = contexto_del_perfil(perfil.activity_type, perfil.geo_zone)
    log_event(
        logger,
        "chat_contexto_perfil",
        interaction_id=str(interaccion.id),
        con_actividad=perfil.activity_type in ETIQUETAS_ACTIVIDAD,
        con_zona="zona:" in contexto,
    )
    return contexto


def _oferta_respaldada(perfil: Profile | None, respuesta: str) -> bool:
    """Indica si las ofertas de la respuesta están respaldadas por el catálogo (Req 16.2).

    Args:
        perfil: Perfil del dueño de la interacción, leído en el servidor; sin
            Perfil, ninguna oferta está respaldada.
        respuesta: texto generado por el modelo.

    Returns:
        True si no hay oferta o si todas las ofertas están en el catálogo del Usuario.
    """
    if not guardrails.menciona_oferta(respuesta):
        return True
    permitidos = nombres_de_ofertas(perfil.activity_type) if perfil else frozenset()
    return guardrails.oferta_respaldada_por_catalogo(
        respuesta, permitidos, nombres_de_todas_las_ofertas()
    )


def _evaluar_salida(perfil: Profile | None, respuesta: str) -> str:
    """Aplica validación de salida y detección de tema sensible (Req 16.2, 16.3).

    Args:
        perfil: Perfil del dueño de la interacción, leído en el servidor.
        respuesta: texto generado por el modelo.

    Returns:
        `GUARDRAIL_PERMITIDO` si la salida puede presentarse, o la decisión del
        guardrail que obliga a usar la respuesta de respaldo.
    """
    respaldada = _oferta_respaldada(perfil, respuesta)
    salida = guardrails.validar_salida(respuesta, oferta_respaldada=respaldada)
    if salida != GUARDRAIL_PERMITIDO:
        return salida
    return guardrails.requiere_derivacion(
        respuesta, confianza=1.0, umbral=STT_CONFIDENCE_THRESHOLD
    )


async def _finalizar_con_respaldo(
    db: AsyncSession,
    interaccion: AiInteraction,
    tts: TextToSpeech,
    decision: str,
    model_version: str | None = None,
) -> None:
    """Deja la interacción en "listo" con la respuesta segura de respaldo.

    Se usa cuando el kill switch está activo, el guardrail bloquea la entrada o
    la salida, o se deriva a canal humano (Req 16.1, 16.2, 16.3, 16.6). La
    respuesta de respaldo se marca como IA y la decisión del guardrail se guarda
    para el registro auditable (Req 16.4). No expone PII.

    Args:
        db: sesión de base de datos.
        interaccion: interacción a finalizar.
        tts: sintetizador de voz para la respuesta de respaldo.
        decision: decisión del guardrail que motivó el respaldo.
        model_version: versión del modelo, si alcanzó a invocarse.
    """
    respuesta = guardrails.marcar_como_ia(SAFE_FALLBACK_RESPONSE)
    interaccion.response_text = respuesta
    interaccion.model_version = model_version
    interaccion.guardrail_decision = decision
    interaccion.response_audio_ref = await _sintetizar_respuesta(tts, respuesta)
    interaccion.status = ESTADO_LISTO
    await db.commit()
    audit.registrar_auditoria(interaccion)


async def _sintetizar_respuesta(tts: TextToSpeech, texto: str) -> str | None:
    """Sintetiza la respuesta como audio (Req 14.3); devuelve su referencia o None.

    El TTS es adicional al texto: si falla, el intercambio conserva la respuesta
    de texto y solo se omite el audio (no se degrada la conversación).

    Args:
        tts: sintetizador de voz.
        texto: respuesta del modelo a sintetizar.

    Returns:
        La referencia al audio generado, o None si no se pudo sintetizar.
    """
    try:
        audio = await tts.synthesize(texto)
    except Exception:
        # El audio es complementario; un fallo del TTS no afecta la respuesta de
        # texto ni el estado "listo". Se registra sin PII.
        log_event(logger, "chat_tts_failed")
        return None
    return audio.audio_ref or None


async def obtener_resultado(
    db: AsyncSession, current_user_id: uuid.UUID, interaction_id: uuid.UUID
) -> ChatMessageResult:
    """Devuelve el estado/resultado de una inferencia del Usuario (Req 3.6-3.8).

    La consulta se ancla al `current_user_id`: una interacción de otro Usuario se
    trata como inexistente, sin revelar su existencia (anti-BOLA).

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado.
        interaction_id: interacción consultada.

    Returns:
        El estado actual y, si está "listo", la respuesta del modelo.

    Raises:
        NotFoundError: si la interacción no existe o no es del Usuario.
    """
    interaccion = await _get_owned(db, current_user_id, interaction_id)
    return ChatMessageResult(
        id=interaccion.id,
        status=interaccion.status,
        input_channel=interaccion.input_channel,
        response_text=interaccion.response_text,
    )


async def obtener_historial(
    db: AsyncSession, current_user_id: uuid.UUID
) -> ChatHistory:
    """Lista el historial de conversación del Usuario autenticado (Req 3.8).

    Solo incluye interacciones del `current_user_id`, ordenadas de la más antigua
    a la más reciente. El contenido ya está redactado (sin PII).

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado.

    Returns:
        El historial del Usuario, sin PII.
    """
    rows = await db.scalars(
        select(AiInteraction)
        .where(AiInteraction.profile_id == current_user_id)
        .order_by(AiInteraction.created_at)
    )
    items = [
        ChatHistoryItem(
            id=i.id,
            status=i.status,
            input_channel=i.input_channel,
            input_redacted=i.input_redacted,
            response_text=i.response_text,
        )
        for i in rows.all()
    ]
    return ChatHistory(items=items)


async def _get_owned(
    db: AsyncSession, current_user_id: uuid.UUID, interaction_id: uuid.UUID
) -> AiInteraction:
    """Obtiene una interacción verificando que pertenezca al Usuario (anti-BOLA).

    Args:
        db: sesión de base de datos.
        current_user_id: Usuario autenticado.
        interaction_id: interacción consultada.

    Returns:
        La interacción si existe y es del Usuario.

    Raises:
        NotFoundError: si no existe o es de otro Usuario (sin distinguir ambos casos).
    """
    interaccion = await db.scalar(
        select(AiInteraction).where(
            AiInteraction.id == interaction_id,
            AiInteraction.profile_id == current_user_id,
        )
    )
    if interaccion is None:
        raise NotFoundError(internal_detail="interaction not found for current user")
    return interaccion
