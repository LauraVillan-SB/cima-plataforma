"""Pruebas de los guardrails y la gobernanza de IA del chat (Tarea 11.5).

Cubren el guardrail de entrada (Req 16.1), la validación de salida de ofertas
(Req 16.2), la derivación por tema sensible o baja confianza (Req 16.3), la
marca reconocible de IA (Req 16.5) y, en el worker, el kill switch (Req 16.6)
con el registro de la decisión del guardrail (Req 16.4). Funciones puras más una
sesión en memoria para el worker. Datos ficticios.
"""
from __future__ import annotations

import uuid

import pytest

from app.chat import guardrails, service
from app.chat.constants import (
    AI_DISCLOSURE_PREFIX,
    ESTADO_ENCOLADO,
    ESTADO_LISTO,
    GUARDRAIL_BLOQUEO_ENTRADA,
    GUARDRAIL_DERIVADO,
    GUARDRAIL_KILL_SWITCH,
    GUARDRAIL_PERMITIDO,
    GUARDRAIL_SALIDA_NO_VALIDADA,
    SAFE_FALLBACK_RESPONSE,
)
from app.chat.dto import ModelResult
from app.chat.models import AiInteraction


# --- Guardrail de entrada (Req 16.1) ---------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "te garantizo ganancias seguras si inviertes",
        "invierte todo tu dinero ya",
        "necesito un prestamo gota a gota",
        "como fabricar un arma casera",
    ],
)
def test_entrada_insegura_se_bloquea(texto: str) -> None:
    """Contenido inseguro o fuera de dominio se bloquea antes del modelo."""
    assert guardrails.evaluar_entrada(texto) == GUARDRAIL_BLOQUEO_ENTRADA


@pytest.mark.parametrize(
    "texto",
    [
        "como protejo mi cultivo de cafe de la sequia",
        "quiero aprender a ahorrar para mi tienda",
        "que es un microseguro",
    ],
)
def test_entrada_valida_se_permite(texto: str) -> None:
    """Las preguntas del dominio educativo pasan el guardrail de entrada."""
    assert guardrails.evaluar_entrada(texto) == GUARDRAIL_PERMITIDO


# --- Validación de salida (Req 16.2) ---------------------------------------


def test_salida_con_oferta_sin_respaldo_no_se_valida() -> None:
    """Una respuesta que ofrece un microseguro sin respaldo del backend se rechaza."""
    salida = guardrails.validar_salida(
        "te ofrezco un microseguro con 50% de descuento", oferta_respaldada=False
    )
    assert salida == GUARDRAIL_SALIDA_NO_VALIDADA


def test_salida_con_oferta_respaldada_se_permite() -> None:
    """Si el backend respalda la oferta, la respuesta se permite."""
    salida = guardrails.validar_salida(
        "tenemos un microseguro para tu cultivo", oferta_respaldada=True
    )
    assert salida == GUARDRAIL_PERMITIDO


def test_salida_sin_oferta_se_permite() -> None:
    """Una respuesta educativa sin ofertas no requiere respaldo."""
    salida = guardrails.validar_salida(
        "para ahorrar, aparta una parte de tus ingresos cada semana",
        oferta_respaldada=False,
    )
    assert salida == GUARDRAIL_PERMITIDO


# --- Derivación (Req 16.3) --------------------------------------------------


def test_tema_sensible_deriva() -> None:
    """Un tema sensible deriva a canal humano / respuesta segura."""
    assert (
        guardrails.requiere_derivacion("tengo pensamientos de suicidio", 1.0, 0.6)
        == GUARDRAIL_DERIVADO
    )


def test_baja_confianza_deriva() -> None:
    """Una respuesta con confianza por debajo del umbral deriva."""
    assert guardrails.requiere_derivacion("respuesta normal", 0.3, 0.6) == GUARDRAIL_DERIVADO


def test_confianza_alta_y_tema_normal_no_deriva() -> None:
    """Un tema del dominio con confianza alta no se deriva."""
    assert (
        guardrails.requiere_derivacion("como siembro maiz", 0.95, 0.6)
        == GUARDRAIL_PERMITIDO
    )


# --- Transparencia de IA (Req 16.5) ----------------------------------------


def test_marca_de_ia_se_antepone() -> None:
    """La respuesta se marca de forma reconocible como IA."""
    marcada = guardrails.marcar_como_ia("hola, con gusto te ayudo")
    assert marcada.startswith(AI_DISCLOSURE_PREFIX)


def test_marca_de_ia_es_idempotente() -> None:
    """Marcar dos veces no duplica el prefijo."""
    una = guardrails.marcar_como_ia("respuesta")
    dos = guardrails.marcar_como_ia(una)
    assert dos == una


# --- Integración en el worker (Req 16.4, 16.6) -----------------------------


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


def _interaccion(texto: str = "como ahorro para mi tienda") -> AiInteraction:
    return AiInteraction(
        id=uuid.uuid4(), profile_id=uuid.uuid4(), input_redacted=texto,
        input_channel="texto", status=ESTADO_ENCOLADO, response_text=None,
        response_audio_ref=None, model_version=None, guardrail_decision=None,
        correlation_id=None, created_at=0,
    )


class _ModeloOk:
    async def generate(self, redacted_text: str) -> ModelResult:
        return ModelResult(text="aparta una parte de tus ingresos", model_version="t-v1")


class _ModeloOfertaInventada:
    async def generate(self, redacted_text: str) -> ModelResult:
        return ModelResult(text="te regalo un microseguro gratis", model_version="t-v1")


@pytest.mark.asyncio
async def test_kill_switch_responde_respaldo_sin_invocar_modelo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con el kill switch activo, el worker no invoca el modelo (Req 16.6)."""
    from app.common import config

    monkeypatch.setattr(
        service, "get_settings",
        lambda: config.Settings(chat_agent_enabled=False),
    )
    db = _FakeSession()
    inter = _interaccion()
    db.rows.append(inter)

    class _ModeloNoDebeLlamarse:
        async def generate(self, redacted_text: str) -> ModelResult:
            raise AssertionError("el modelo no debe invocarse con kill switch activo")

    await service.procesar_inferencia(db, inter.id, modelo=_ModeloNoDebeLlamarse())
    assert inter.status == ESTADO_LISTO
    assert inter.guardrail_decision == GUARDRAIL_KILL_SWITCH
    assert SAFE_FALLBACK_RESPONSE in inter.response_text


@pytest.mark.asyncio
async def test_entrada_bloqueada_no_invoca_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una entrada insegura se responde con respaldo sin invocar el modelo (Req 16.1)."""
    from app.common import config

    monkeypatch.setattr(service, "get_settings", lambda: config.Settings())
    db = _FakeSession()
    inter = _interaccion("te garantizo ganancias si inviertes todo")
    db.rows.append(inter)

    class _ModeloNoDebeLlamarse:
        async def generate(self, redacted_text: str) -> ModelResult:
            raise AssertionError("no debe invocarse con entrada bloqueada")

    await service.procesar_inferencia(db, inter.id, modelo=_ModeloNoDebeLlamarse())
    assert inter.guardrail_decision == GUARDRAIL_BLOQUEO_ENTRADA
    assert SAFE_FALLBACK_RESPONSE in inter.response_text


@pytest.mark.asyncio
async def test_salida_con_oferta_inventada_se_deriva(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el modelo inventa una oferta, la respuesta se reemplaza por el respaldo (Req 16.2)."""
    from app.common import config

    monkeypatch.setattr(service, "get_settings", lambda: config.Settings())
    db = _FakeSession()
    inter = _interaccion()
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_ModeloOfertaInventada())
    assert inter.guardrail_decision == GUARDRAIL_SALIDA_NO_VALIDADA
    assert "microseguro gratis" not in inter.response_text
    assert SAFE_FALLBACK_RESPONSE in inter.response_text


@pytest.mark.asyncio
async def test_respuesta_valida_se_marca_como_ia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una respuesta válida pasa los guardrails, se marca como IA y queda permitida."""
    from app.common import config

    monkeypatch.setattr(service, "get_settings", lambda: config.Settings())
    db = _FakeSession()
    inter = _interaccion()
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_ModeloOk())
    assert inter.status == ESTADO_LISTO
    assert inter.guardrail_decision == GUARDRAIL_PERMITIDO
    assert inter.response_text.startswith(AI_DISCLOSURE_PREFIX)
