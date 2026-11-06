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

from app.chat.constants import (
    CANAL_VOZ,
    ESTADO_ENCOLADO,
    ESTADO_ERROR,
    ESTADO_LISTO,
    ESTADO_PROCESANDO,
    ESTADO_REPETIR_VOZ,
    INFERENCE_TIMEOUT_SECONDS,
    PROCESSING_INDICATOR_SECONDS,
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
    SafeFallbackModel,
    SpeechToText,
    TextToSpeech,
    UnavailableStt,
)
from app.chat.models import AiInteraction
from app.chat.redaction import redactar_pii
from app.chat.validation import validar_mensaje_texto, validar_nota_de_voz
from app.common.correlation import get_correlation_id
from app.common.errors import NotFoundError
from app.common.logging import log_event
from app.common.resilience import CircuitBreaker

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
    stt = stt or UnavailableStt()

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
        modelo: modelo de IA a usar; por defecto, el de respaldo seguro.
    """
    modelo = modelo or SafeFallbackModel()
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

    async def _invocar() -> object:
        return await modelo.generate(texto_redactado)

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
        log_event(logger, "chat_inference_failed", interaction_id=str(interaction_id))
        return

    interaccion.response_text = resultado.text
    interaccion.model_version = resultado.model_version
    interaccion.response_audio_ref = await _sintetizar_respuesta(tts, resultado.text)
    interaccion.status = ESTADO_LISTO
    await db.commit()
    log_event(
        logger,
        "chat_inference_completed",
        interaction_id=str(interaction_id),
        model_version=resultado.model_version,
        con_audio=bool(interaccion.response_audio_ref),
    )


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
