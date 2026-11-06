"""Pruebas del registro auditable de interacciones de IA (Tarea 11.6).

Cubren que el registro incluya la entrada redactada, la salida, la versión del
modelo y la decisión del guardrail (Req 16.4), que no exponga PII ni el
`profile_id` (Req 3.9), y que el worker emita exactamente un evento auditable al
finalizar, tanto en el camino exitoso como en el de respaldo. Captura el evento
sustituyendo `log_event`; no usa logging real ni BD.
"""
from __future__ import annotations

import uuid

import pytest

from app.chat import audit, service
from app.chat.constants import (
    ESTADO_ENCOLADO,
    ESTADO_LISTO,
    GUARDRAIL_KILL_SWITCH,
    GUARDRAIL_PERMITIDO,
)
from app.chat.dto import ModelResult
from app.chat.models import AiInteraction


def _interaccion(**kw) -> AiInteraction:
    base = dict(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        input_redacted="como ahorro para mi tienda",
        input_channel="texto",
        status=ESTADO_LISTO,
        response_text="aparta una parte cada semana",
        response_audio_ref=None,
        model_version="t-v1",
        guardrail_decision=GUARDRAIL_PERMITIDO,
        correlation_id="corr-1",
        created_at=0,
    )
    base.update(kw)
    return AiInteraction(**base)


def _capturar(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """Sustituye `log_event` del módulo de auditoría y captura los eventos."""
    eventos: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        audit, "log_event", lambda _logger, mensaje, **ctx: eventos.append((mensaje, ctx))
    )
    return eventos


# --- Contenido del registro (Req 16.4) -------------------------------------


def test_registro_incluye_campos_auditables(monkeypatch: pytest.MonkeyPatch) -> None:
    """El registro lleva entrada redactada, salida, versión y decisión del guardrail."""
    eventos = _capturar(monkeypatch)
    inter = _interaccion()
    audit.registrar_auditoria(inter)
    assert len(eventos) == 1
    mensaje, ctx = eventos[0]
    assert mensaje == "chat_ai_interaction_audit"
    assert ctx["input_redacted"] == "como ahorro para mi tienda"
    assert ctx["response"] == "aparta una parte cada semana"
    assert ctx["model_version"] == "t-v1"
    assert ctx["guardrail_decision"] == GUARDRAIL_PERMITIDO
    assert ctx["interaction_id"] == str(inter.id)


def test_registro_no_incluye_profile_id_ni_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """El registro no expone el profile_id ni ninguna PII (Req 3.9)."""
    eventos = _capturar(monkeypatch)
    inter = _interaccion(profile_id=uuid.uuid4())
    audit.registrar_auditoria(inter)
    _, ctx = eventos[0]
    # El profile_id no aparece en ninguna clave ni valor del registro.
    assert "profile_id" not in ctx
    assert str(inter.profile_id) not in str(ctx)


def test_registro_acota_contenido_largo(monkeypatch: pytest.MonkeyPatch) -> None:
    """El contenido registrado se acota para no generar logs desproporcionados."""
    eventos = _capturar(monkeypatch)
    inter = _interaccion(input_redacted="a" * 5000)
    audit.registrar_auditoria(inter)
    _, ctx = eventos[0]
    assert len(ctx["input_redacted"]) == 2000


def test_registro_tolera_salida_nula(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una interacción en error (sin respuesta) se registra con response=None."""
    eventos = _capturar(monkeypatch)
    inter = _interaccion(status="error", response_text=None, model_version=None)
    audit.registrar_auditoria(inter)
    _, ctx = eventos[0]
    assert ctx["response"] is None
    assert ctx["status"] == "error"


# --- Integración en el worker ----------------------------------------------


class _FakeSession:
    def __init__(self) -> None:
        self.rows: list[AiInteraction] = []

    def add(self, obj: object) -> None:
        if isinstance(obj, AiInteraction) and obj not in self.rows:
            self.rows.append(obj)

    async def commit(self) -> None:
        return None

    async def get(self, _model, pk):  # noqa: ANN001 - stub
        return next((r for r in self.rows if r.id == pk), None)


class _ModeloOk:
    async def generate(self, redacted_text: str) -> ModelResult:
        return ModelResult(text="una respuesta util", model_version="t-v1")


@pytest.mark.asyncio
async def test_worker_registra_auditoria_al_finalizar(monkeypatch: pytest.MonkeyPatch) -> None:
    """El camino exitoso emite exactamente un registro auditable (Req 16.4)."""
    from app.common import config

    monkeypatch.setattr(service, "get_settings", lambda: config.Settings())
    eventos = _capturar(monkeypatch)
    db = _FakeSession()
    inter = _interaccion(status=ESTADO_ENCOLADO, response_text=None, model_version=None)
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_ModeloOk())
    auditorias = [e for e in eventos if e[0] == "chat_ai_interaction_audit"]
    assert len(auditorias) == 1
    assert auditorias[0][1]["guardrail_decision"] == GUARDRAIL_PERMITIDO


@pytest.mark.asyncio
async def test_worker_registra_auditoria_en_respaldo(monkeypatch: pytest.MonkeyPatch) -> None:
    """El camino de respaldo (kill switch) también emite el registro auditable."""
    from app.common import config

    monkeypatch.setattr(
        service, "get_settings", lambda: config.Settings(chat_agent_enabled=False)
    )
    eventos = _capturar(monkeypatch)
    db = _FakeSession()
    inter = _interaccion(status=ESTADO_ENCOLADO, response_text=None, model_version=None)
    db.rows.append(inter)

    class _ModeloNoDebeLlamarse:
        async def generate(self, redacted_text: str) -> ModelResult:
            raise AssertionError("no debe invocarse con kill switch")

    await service.procesar_inferencia(db, inter.id, modelo=_ModeloNoDebeLlamarse())
    auditorias = [e for e in eventos if e[0] == "chat_ai_interaction_audit"]
    assert len(auditorias) == 1
    assert auditorias[0][1]["guardrail_decision"] == GUARDRAIL_KILL_SWITCH
