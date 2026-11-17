"""Reglas de la encuesta: ruta completa, encuesta vigente, comentario sin PII.

Feature: cima-plataforma.
- Req 20.1: la encuesta se presenta y se registra solo para una ruta completada y
  con una encuesta activa, con una calificación de 1 a 5.
- Req 20.3/20.4: el comentario es el único campo abierto, con allowlist y largo
  máximo; lo inválido se rechaza sin registrar.
- Req 20.5: el comentario se guarda con la PII redactada.
- Req 20.7: una sola respuesta por Usuario y ruta.

Sin BD real: reutiliza el stub de sesión de `test_idempotencia`.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.common.database import get_session
from app.common.errors import NotFoundError
from app.common.security import get_current_user_id
from app.learning.catalog import PATHS
from app.learning.seed import seed_catalog, survey_id
from app.main import app
from app.survey import service
from app.survey.constants import (
    COMMENT_MAX_LENGTH,
    QUESTION_TYPE_RATING,
    QUESTION_TYPE_TEXT,
    SURVEY_QUESTIONS,
)
from app.survey.dto import SurveyResponseCreate
from app.survey.errors import (
    EncuestaYaRespondidaError,
    RutaNoCompletadaParaEncuestaError,
)
from app.survey.models import SurveyResponse
from tests.survey.test_idempotencia import _FakeSession, _survey


def _respuesta(user: uuid.UUID, **kw: object) -> SurveyResponseCreate:
    base: dict = {"client_event_id": uuid.uuid4(), "profile_id": user, "rating": 4}
    base.update(kw)
    return SurveyResponseCreate(**base)


# --------------------------------------------------------------------------- #
# Ruta completa y encuesta vigente (Req 20.1)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sin_la_ruta_completa_no_se_presenta_ni_se_registra() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [], ruta_completa=False)

    with pytest.raises(RutaNoCompletadaParaEncuestaError):
        await service.present_survey(sesion, path, user)
    with pytest.raises(RutaNoCompletadaParaEncuestaError):
        await service.record_response(sesion, path, user, _respuesta(user))
    assert sesion._responses == [] and sesion.committed == 0


@pytest.mark.asyncio
async def test_sin_encuesta_activa_no_se_registra() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(None, [])

    with pytest.raises(NotFoundError):
        await service.record_response(sesion, path, user, _respuesta(user))
    assert sesion._responses == []


@pytest.mark.asyncio
async def test_una_segunda_respuesta_distinta_se_rechaza_con_mensaje_claro() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])
    await service.record_response(sesion, path, user, _respuesta(user))

    with pytest.raises(EncuestaYaRespondidaError):
        await service.record_response(sesion, path, user, _respuesta(user))
    assert len(sesion._responses) == 1
    assert EncuestaYaRespondidaError.status_code == 409


# --------------------------------------------------------------------------- #
# Comentario: allowlist, largo y PII (Req 20.3–20.5)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_el_comentario_se_guarda_con_la_pii_redactada() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])
    # Datos ficticios: no son de ninguna persona real.
    comentario = "Muy útil. Me llamo Rosa y mi celular es 300 123 4567, escríbanme a rosa@correo.com"

    await service.record_response(
        sesion, path, user, _respuesta(user, answers={"comentario": comentario})
    )

    guardado = sesion._responses[0].answers["comentario"]
    assert "Rosa" not in guardado
    assert "300 123 4567" not in guardado and "4567" not in guardado
    assert "rosa@correo.com" not in guardado
    assert guardado.startswith("Muy útil.")


@pytest.mark.asyncio
async def test_sin_comentario_no_se_guardan_respuestas_abiertas() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])

    await service.record_response(sesion, path, user, _respuesta(user, answers={"comentario": "   "}))

    assert sesion._responses[0].answers == {}


@pytest.mark.parametrize(
    "answers",
    [
        {"otra": "x"},  # campo fuera de la allowlist
        {"comentario": "x" * (COMMENT_MAX_LENGTH + 1)},  # demasiado largo
        {"comentario": 5},  # tipo inesperado
        {"comentario": "hola", "telefono": "3001234567"},
    ],
)
def test_respuestas_abiertas_invalidas_se_rechazan(answers: dict) -> None:
    with pytest.raises(PydanticValidationError):
        SurveyResponseCreate(
            client_event_id=uuid.uuid4(), profile_id=uuid.uuid4(), rating=3, answers=answers
        )


@settings(max_examples=150, deadline=None)
@given(comentario=st.text(max_size=COMMENT_MAX_LENGTH))
@pytest.mark.asyncio
async def test_lo_guardado_nunca_trae_un_celular_ni_un_correo(comentario: str) -> None:
    """Para cualquier comentario válido, lo guardado no tiene PII detectable o no se guarda."""
    from app.chat.redaction import contiene_pii
    from app.survey.errors import ComentarioConDatosPersonalesError

    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])
    try:
        await service.record_response(
            sesion, path, user, _respuesta(user, answers={"comentario": comentario})
        )
    except ComentarioConDatosPersonalesError:
        assert sesion._responses == []
        return
    guardado = sesion._responses[0].answers.get("comentario", "")
    assert not contiene_pii(guardado)


# --------------------------------------------------------------------------- #
# Encuesta estándar y carga (Req 20.1)
# --------------------------------------------------------------------------- #
def test_la_encuesta_estandar_tiene_una_calificacion_y_un_comentario() -> None:
    tipos = [q["type"] for q in SURVEY_QUESTIONS]
    assert tipos.count(QUESTION_TYPE_RATING) == 1
    assert tipos.count(QUESTION_TYPE_TEXT) == 1
    assert all(q["id"] and q["text"] for q in SURVEY_QUESTIONS)


class _SeedSession:
    def __init__(self) -> None:
        self.sentencias: list = []

    async def execute(self, stmt) -> None:  # noqa: ANN001
        self.sentencias.append(stmt)

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_la_carga_crea_una_encuesta_por_ruta_con_id_estable() -> None:
    sesion = _SeedSession()

    resultado = await seed_catalog(sesion)

    assert resultado.surveys == len(PATHS)
    encuestas = [s for s in sesion.sentencias if "surveys" in str(s)]
    assert len(encuestas) == len(PATHS)
    assert survey_id(PATHS[0]) == survey_id(PATHS[0])
    assert len({survey_id(p) for p in PATHS}) == len(PATHS)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def _cliente(user: uuid.UUID, sesion: object) -> TestClient:
    async def _db():  # noqa: ANN202
        yield sesion

    app.dependency_overrides[get_current_user_id] = lambda: user
    app.dependency_overrides[get_session] = _db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpiar_overrides():
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_session, None)


def test_get_sin_ruta_completa_responde_409_con_mensaje_claro() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    respuesta = _cliente(user, _FakeSession(_survey(path), [], ruta_completa=False)).get(
        f"/api/v1/encuestas/{path}"
    )

    assert respuesta.status_code == 409
    assert "termines todas las lecciones" in respuesta.json()["detail"]


def test_post_con_un_campo_extra_en_answers_responde_422_sin_registrar() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])
    cuerpo = {
        "client_event_id": str(uuid.uuid4()),
        "profile_id": str(user),
        "rating": 5,
        "answers": {"comentario": "bien", "cedula": "1234567890"},
    }

    respuesta = _cliente(user, sesion).post(f"/api/v1/encuestas/{path}/respuestas", json=cuerpo)

    assert respuesta.status_code == 422
    assert sesion._responses == []


def test_post_valido_responde_201_y_no_devuelve_el_comentario() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    sesion = _FakeSession(_survey(path), [])
    cuerpo = {
        "client_event_id": str(uuid.uuid4()),
        "profile_id": str(user),
        "rating": 5,
        "answers": {"comentario": "Me gustó mucho"},
        "geo_zone": "Huila",
    }

    respuesta = _cliente(user, sesion).post(f"/api/v1/encuestas/{path}/respuestas", json=cuerpo)

    assert respuesta.status_code == 201
    assert set(respuesta.json()) == {"id", "path_id", "rating", "geo_zone"}
    assert isinstance(sesion._responses[0], SurveyResponse)
