"""Pruebas de la inferencia asíncrona del Conversational Agent Service (Tarea 11.3).

Cubren: encolado con respuesta 202 e idempotencia (Req 3.5), rechazo por
validación de longitud (11.1), redacción de PII antes de persistir (11.2),
cálculo del indicador de procesamiento y del timeout de 60 s (Req 3.7, 3.8),
historial del Usuario, y anti-BOLA (no se expone el mensaje de otro Usuario).

No usan BD real: un stub de sesión en memoria resuelve `ChatMessage` por
`client_event_id` o por id, guarda lo añadido y simula commit/refresh. La cola
de inferencia es nula (no procesa). Identificadores y textos ficticios.

La no-emisión al modelo cuando la redacción de PII falla se prueba a nivel de
`redactar_pii` en `tests/chat/test_redaction.py`; aquí se verifica que la
entrada se persiste ya redactada.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.chat import service
from app.chat.constants import (
    INFERENCE_TIMEOUT_SECONDS,
    MSG_STATUS_FALLIDO,
    MSG_STATUS_LISTO,
    MSG_STATUS_PENDIENTE,
    PROCESSING_INDICATOR_SECONDS,
    TEXT_MAX_LENGTH,
)
from app.chat.dto import ChatMessageEnqueueIn
from app.chat.errors import MensajeInvalidoError
from app.chat.models import AiInteraction, ChatMessage
from app.chat.service import NullInferenceQueue
from app.common.errors import NotFoundError

_USER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _mensaje(
    *,
    profile_id: uuid.UUID = _USER_ID,
    status: str = MSG_STATUS_PENDIENTE,
    created_at: datetime | None = None,
    response: str | None = None,
) -> ChatMessage:
    """Crea un ChatMessage ficticio con entrada ya redactada."""
    return ChatMessage(
        id=uuid.uuid4(),
        client_event_id=uuid.uuid4(),
        profile_id=profile_id,
        source="texto",
        redacted_input="hola, tengo una duda",
        response=response,
        status=status,
        created_at=created_at or datetime.now(timezone.utc),
    )


class _FakeSession:
    """Sesión async que resuelve ChatMessage por client_event_id o por id."""

    def __init__(
        self,
        por_evento: ChatMessage | None = None,
        almacenados: list[ChatMessage] | None = None,
    ) -> None:
        self._por_evento = por_evento
        self._almacenados = list(almacenados or [])
        self.added: list[object] = []
        self.commits = 0

    async def scalar(self, stmt):  # noqa: ANN001 - distingue consulta por el WHERE
        sql = str(stmt).lower()
        # La consulta de idempotencia filtra por client_event_id.
        if "client_event_id" in sql:
            return self._por_evento
        return self._almacenados[0] if self._almacenados else None

    async def scalars(self, _stmt):  # noqa: ANN001 - historial del Usuario
        return _ScalarResult(self._almacenados)

    async def get(self, _model, pk):  # noqa: ANN001
        for m in self._almacenados:
            if m.id == pk:
                return m
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, ChatMessage):
            self._almacenados.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: object) -> None:
        if isinstance(obj, ChatMessage) and obj.id is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, ChatMessage) and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)


class _ScalarResult:
    def __init__(self, items: list[ChatMessage]) -> None:
        self._items = items

    def all(self) -> list[ChatMessage]:
        return list(self._items)


def _in(text: str) -> ChatMessageEnqueueIn:
    return ChatMessageEnqueueIn(client_event_id=uuid.uuid4(), text=text)


# --- Encolado (Req 3.5) -----------------------------------------------------


@pytest.mark.asyncio
async def test_encola_mensaje_valido_queda_pendiente() -> None:
    """Un mensaje válido se persiste pendiente y registra la interacción (Req 3.5, 3.9)."""
    db = _FakeSession()
    out = await service.encolar_mensaje_texto(
        db, _USER_ID, _in("Hola, ¿qué es un microseguro?"), NullInferenceQueue()
    )
    assert out.status == MSG_STATUS_PENDIENTE
    assert out.response is None
    # Se persistió el mensaje y se registró la interacción auditable (sin PII).
    assert any(isinstance(o, ChatMessage) for o in db.added)
    assert any(isinstance(o, AiInteraction) for o in db.added)


@pytest.mark.asyncio
async def test_encolar_es_idempotente_por_client_event_id() -> None:
    """Un reenvío con el mismo client_event_id devuelve el existente sin duplicar (Req 3.5)."""
    previo = _mensaje()
    db = _FakeSession(por_evento=previo)
    out = await service.encolar_mensaje_texto(
        db, _USER_ID, _in("otra vez"), NullInferenceQueue()
    )
    assert out.id == previo.id
    # No se añadió un nuevo ChatMessage.
    assert not any(isinstance(o, ChatMessage) for o in db.added)


@pytest.mark.asyncio
async def test_rechaza_texto_vacio_sin_encolar() -> None:
    """Un texto vacío tras trim se rechaza por validación (11.1) y no se encola (Req 3.2)."""
    db = _FakeSession()
    with pytest.raises(MensajeInvalidoError):
        await service.encolar_mensaje_texto(db, _USER_ID, _in("    "), NullInferenceQueue())
    assert db.added == []


@pytest.mark.asyncio
async def test_rechaza_texto_demasiado_largo_sin_encolar() -> None:
    """Un texto > 2000 caracteres se rechaza sin encolar (Req 3.2)."""
    db = _FakeSession()
    with pytest.raises(MensajeInvalidoError):
        await service.encolar_mensaje_texto(
            db, _USER_ID, _in("a" * (TEXT_MAX_LENGTH + 1)), NullInferenceQueue()
        )
    assert db.added == []


@pytest.mark.asyncio
async def test_persiste_la_entrada_ya_redactada() -> None:
    """La entrada se redacta antes de persistir: no queda PII en lo guardado (Req 3.10)."""
    db = _FakeSession()
    out = await service.encolar_mensaje_texto(
        db, _USER_ID, _in("escríbeme a juan@correo.com por favor"), NullInferenceQueue()
    )
    assert out.status == MSG_STATUS_PENDIENTE
    # El correo original fue reemplazado por un marcador; no se persiste PII.
    assert "@correo.com" not in out.redacted_input
    assert "[CORREO]" in out.redacted_input


# --- Estado: indicador y timeout (Req 3.7, 3.8) -----------------------------


@pytest.mark.asyncio
async def test_indicador_de_procesamiento_tras_umbral() -> None:
    """A partir de 15 s sin respuesta, el estado pide mostrar el indicador (Req 3.7)."""
    antiguo = _mensaje(
        created_at=datetime.now(timezone.utc)
        - timedelta(seconds=PROCESSING_INDICATOR_SECONDS + 1)
    )
    db = _FakeSession(almacenados=[antiguo])
    out = await service.obtener_estado_mensaje(db, _USER_ID, antiguo.id)
    assert out.show_indicator is True
    assert out.status == MSG_STATUS_PENDIENTE  # aún no supera el timeout


@pytest.mark.asyncio
async def test_timeout_marca_fallido_conservando_historial() -> None:
    """Pasados 60 s sin respuesta, el mensaje se marca fallido (Req 3.8)."""
    vencido = _mensaje(
        created_at=datetime.now(timezone.utc)
        - timedelta(seconds=INFERENCE_TIMEOUT_SECONDS + 1)
    )
    db = _FakeSession(almacenados=[vencido])
    out = await service.obtener_estado_mensaje(db, _USER_ID, vencido.id)
    assert out.status == MSG_STATUS_FALLIDO
    # El mensaje sigue existiendo (historial conservado).
    assert vencido in db._almacenados


@pytest.mark.asyncio
async def test_mensaje_listo_no_muestra_indicador() -> None:
    """Un mensaje ya listo no pide indicador ni se marca fallido."""
    listo = _mensaje(status=MSG_STATUS_LISTO, response="Un microseguro es...")
    db = _FakeSession(almacenados=[listo])
    out = await service.obtener_estado_mensaje(db, _USER_ID, listo.id)
    assert out.status == MSG_STATUS_LISTO
    assert out.show_indicator is False
    assert out.response == "Un microseguro es..."


# --- Anti-BOLA e historial --------------------------------------------------


@pytest.mark.asyncio
async def test_no_expone_mensaje_de_otro_usuario() -> None:
    """Consultar un mensaje de otro Usuario se trata como inexistente (anti-BOLA)."""
    ajeno = _mensaje(profile_id=uuid.uuid4())
    db = _FakeSession(almacenados=[ajeno])
    with pytest.raises(NotFoundError):
        await service.obtener_estado_mensaje(db, _USER_ID, ajeno.id)


@pytest.mark.asyncio
async def test_historial_del_usuario() -> None:
    """El historial devuelve los mensajes del Usuario autenticado, sin PII."""
    db = _FakeSession(
        almacenados=[_mensaje(), _mensaje(status=MSG_STATUS_LISTO, response="ok")]
    )
    hist = await service.obtener_historial(db, _USER_ID)
    assert len(hist.items) == 2
    for item in hist.items:
        assert "@" not in item.redacted_input  # entrada ya redactada
