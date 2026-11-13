"""Pruebas de la validación de ofertas del chat contra el catálogo (Req 16.2, 5.4).

Cubre el catálogo puro, la decisión pura del guardrail y su integración en el
worker con una sesión falsa (sin BD ni red).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.chat import guardrails, service
from app.chat.constants import (
    ESTADO_ENCOLADO,
    ESTADO_LISTO,
    GUARDRAIL_PERMITIDO,
    GUARDRAIL_SALIDA_NO_VALIDADA,
)
from app.chat.dto import ModelResult
from app.chat.models import AiInteraction
from app.conversion.catalog import (
    nombres_de_ofertas,
    nombres_de_todas_las_ofertas,
    normalizar_texto,
)
from app.profile.models import Profile

CAFE = nombres_de_ofertas("cafe")
TODOS = nombres_de_todas_las_ofertas()


# --- Catálogo puro ----------------------------------------------------------


def test_normalizar_texto_quita_tildes_y_mayusculas() -> None:
    """La normalización elimina tildes, mayúsculas y espacios repetidos."""
    assert normalizar_texto("  Protección   CLIMÁTICA ") == "proteccion climatica"


def test_nombres_de_ofertas_por_actividad() -> None:
    """Un cultivo del catálogo devuelve sus nombres normalizados."""
    assert "proteccion climatica para cafe" in CAFE
    assert "amparo de cosecha" in CAFE


def test_nombres_de_ofertas_actividad_desconocida_es_vacio() -> None:
    """Una actividad sin oferta devuelve conjunto vacío (Req 5.8)."""
    assert nombres_de_ofertas("otra") == frozenset()


def test_todos_incluye_ofertas_de_otras_actividades() -> None:
    """El conjunto global contiene productos de todos los tipos de actividad."""
    assert CAFE < TODOS
    assert "amparo del ganado" in TODOS


# --- Decisión pura ----------------------------------------------------------


def test_sin_oferta_es_valida() -> None:
    """Una respuesta sin oferta no necesita respaldo."""
    assert guardrails.oferta_respaldada_por_catalogo("aparta algo cada semana", CAFE, TODOS)


def test_producto_del_catalogo_del_usuario_es_valido() -> None:
    """Nombrar un microseguro de su propio catálogo está respaldado."""
    texto = "Hay un microseguro llamado Protección climática para café."
    assert guardrails.oferta_respaldada_por_catalogo(texto, CAFE, TODOS)


def test_microseguro_generico_con_catalogo_es_valido() -> None:
    """Mencionar microseguros sin nombrar productos ajenos es válido."""
    assert guardrails.oferta_respaldada_por_catalogo("Existen microseguros para ti", CAFE, TODOS)


def test_producto_de_otra_actividad_se_rechaza() -> None:
    """Un producto de otro tipo de actividad no está respaldado para el Usuario."""
    texto = "Te recomiendo el microseguro Amparo del ganado."
    assert not guardrails.oferta_respaldada_por_catalogo(texto, CAFE, TODOS)


def test_usuario_sin_catalogo_se_rechaza() -> None:
    """Sin ofertas para su actividad, cualquier microseguro es inventado."""
    assert not guardrails.oferta_respaldada_por_catalogo(
        "Tenemos un microseguro", frozenset(), TODOS
    )


@pytest.mark.parametrize(
    "texto",
    [
        "Un microseguro por $ 5000 al mes",
        "Un microseguro con 50% menos",
        "Un microseguro de 20.000 pesos",
    ],
)
def test_ofertas_con_cifras_se_rechazan(texto: str) -> None:
    """El catálogo no tiene precios: una oferta con cifras es inventada."""
    assert not guardrails.oferta_respaldada_por_catalogo(texto, CAFE, TODOS)


@pytest.mark.parametrize(
    "texto",
    [
        "Tu microseguro viene con un incentivo",
        "Tienes descuento en el microseguro",
        "Una promoción exclusiva",
    ],
)
def test_incentivos_y_descuentos_nunca_estan_respaldados(texto: str) -> None:
    """Incentivos, descuentos y promociones no provienen del catálogo."""
    assert not guardrails.oferta_respaldada_por_catalogo(texto, CAFE, TODOS)


# --- Integración en el worker ----------------------------------------------


class _FakeSession:
    """Sesión falsa: devuelve el Perfil configurado y registra las lecturas."""

    def __init__(self, activity_type: str | None) -> None:
        self.rows: list[AiInteraction] = []
        self.activity_type = activity_type
        self.perfil_consultado = 0

    def add(self, obj: object) -> None:
        if isinstance(obj, AiInteraction) and obj not in self.rows:
            self.rows.append(obj)

    async def commit(self) -> None:
        return None

    async def get(self, modelo, pk):  # noqa: ANN001 - stub
        if modelo is Profile:
            self.perfil_consultado += 1
            if self.activity_type is None:
                return None
            return SimpleNamespace(id=pk, activity_type=self.activity_type, geo_zone="Huila")
        return next((r for r in self.rows if r.id == pk), None)


class _Modelo:
    def __init__(self, texto: str) -> None:
        self.texto = texto

    async def generate(self, redacted_text: str) -> ModelResult:
        return ModelResult(text=self.texto, model_version="t-v1")


async def _procesar(
    monkeypatch: pytest.MonkeyPatch, activity_type: str | None, texto: str
) -> tuple[_FakeSession, AiInteraction]:
    from app.common import config

    monkeypatch.setattr(service, "get_settings", lambda: config.Settings())
    db = _FakeSession(activity_type)
    inter = AiInteraction(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        input_redacted="que seguro me sirve",
        input_channel="texto",
        status=ESTADO_ENCOLADO,
        correlation_id="corr-1",
        created_at=0,
    )
    db.rows.append(inter)
    await service.procesar_inferencia(db, inter.id, modelo=_Modelo(texto))
    return db, inter


@pytest.mark.asyncio
async def test_worker_permite_oferta_del_catalogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una oferta del catálogo del Usuario se presenta tal cual."""
    _, inter = await _procesar(
        monkeypatch, "cafe", "Existe el microseguro Amparo de cosecha para tu cafetal."
    )
    assert inter.status == ESTADO_LISTO
    assert inter.guardrail_decision == GUARDRAIL_PERMITIDO


@pytest.mark.asyncio
async def test_worker_rechaza_oferta_inventada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un microseguro con precio inventado se reemplaza por la respuesta segura."""
    _, inter = await _procesar(
        monkeypatch, "cafe", "Te damos un microseguro con 50% de descuento."
    )
    assert inter.guardrail_decision == GUARDRAIL_SALIDA_NO_VALIDADA


@pytest.mark.asyncio
async def test_worker_rechaza_oferta_si_no_hay_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el Perfil no existe, ninguna oferta está respaldada."""
    _, inter = await _procesar(monkeypatch, None, "Tenemos un microseguro para ti.")
    assert inter.guardrail_decision == GUARDRAIL_SALIDA_NO_VALIDADA


@pytest.mark.asyncio
async def test_worker_consulta_el_perfil_una_sola_vez(monkeypatch: pytest.MonkeyPatch) -> None:
    """El Perfil se lee una vez por interacción: para el contexto del prompt
    (Req 4.8, 6.7) y, si hay oferta, para validarla, sin una segunda lectura."""
    db, inter = await _procesar(monkeypatch, "cafe", "Aparta una parte cada semana.")
    assert db.perfil_consultado == 1
    assert inter.guardrail_decision == GUARDRAIL_PERMITIDO

    db, inter = await _procesar(
        monkeypatch, "cafe", "Existe el microseguro Amparo de cosecha para tu cafetal."
    )
    assert db.perfil_consultado == 1
    assert inter.guardrail_decision == GUARDRAIL_PERMITIDO
