"""Pruebas de propiedad de idempotencia de presentación/registro de encuesta.

Feature: cima-plataforma, Property 44: Idempotencia de presentación/registro de
la encuesta.
Validates: Requirements 20.6

El stub de sesión inspecciona la sentencia SQLAlchemy recibida para distinguir
las consultas del servicio (sobre `Survey` o sobre `SurveyResponse`, y en este
caso por `client_event_id` o por `(profile_id, path_id)`), devolviendo lo que
corresponda desde el estado en memoria. No hay BD real.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.survey import service
from app.survey.dto import SurveyResponseCreate
from app.survey.models import Survey, SurveyResponse


def _stmt_text(stmt) -> str:
    """Representación textual de la sentencia para inspeccionar sus columnas."""
    return str(stmt)


class _FakeSession:
    """Sesión async que resuelve los `scalar` del Survey Service por inspección.

    El Survey Service construye tres consultas distinguibles por su texto:
    - `select(Survey)...`            -> encuesta activa de la ruta
    - `select(SurveyResponse)...client_event_id` -> respuesta por evento
    - `select(SurveyResponse.id)...` -> respuesta previa por (usuario, ruta)
    """

    def __init__(self, survey: Survey, responses: list[SurveyResponse]) -> None:
        self._survey = survey
        self._responses = responses
        self.committed = 0

    async def scalar(self, stmt):
        texto = _stmt_text(stmt)
        if "surveys" in texto and "survey_responses" not in texto:
            return self._survey if self._survey.active else None
        if "client_event_id" in texto:
            # Consulta por client_event_id; extraemos el valor del binding.
            event_id = _bind_value(stmt, "client_event_id")
            return next(
                (r for r in self._responses if str(r.client_event_id) == str(event_id)),
                None,
            )
        # Consulta por (profile_id, path_id): devuelve el id si existe.
        profile_id = _bind_value(stmt, "profile_id")
        path_id = _bind_value(stmt, "path_id")
        found = next(
            (
                r
                for r in self._responses
                if str(r.profile_id) == str(profile_id)
                and str(r.path_id) == str(path_id)
            ),
            None,
        )
        return found.id if found else None

    def add(self, obj: SurveyResponse) -> None:
        # El ORM asigna `id` por `default=uuid.uuid4` en el flush; lo simulamos.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._responses.append(obj)

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, _obj) -> None:
        return None


def _bind_value(stmt, column: str):
    """Extrae el valor enlazado a una columna del WHERE de la sentencia."""
    params = stmt.compile().params
    for key, value in params.items():
        if key.startswith(column):
            return value
    return None


def _survey(path_id: uuid.UUID) -> Survey:
    return Survey(
        id=uuid.uuid4(),
        path_id=path_id,
        questions={"questions": [{"id": "q1", "text": "¿Te sirvió?", "type": "rating"}]},
        active=True,
    )


# Feature: cima-plataforma, Property 44: Idempotencia de presentación/registro.
# Validates: Requirements 20.6
@settings(max_examples=50, deadline=None)
@given(rating=st.integers(min_value=1, max_value=5))
@pytest.mark.asyncio
async def test_property_44_mismo_client_event_id_no_duplica(rating: int) -> None:
    """Reintentar con el mismo `client_event_id` devuelve la misma respuesta."""
    user_id = uuid.uuid4()
    path_id = uuid.uuid4()
    event_id = uuid.uuid4()
    sesion = _FakeSession(_survey(path_id), [])

    data = SurveyResponseCreate(
        client_event_id=event_id,
        profile_id=user_id,
        rating=rating,
        answers={},
    )

    primera = await service.record_response(sesion, path_id, user_id, data)
    segunda = await service.record_response(sesion, path_id, user_id, data)

    assert primera.id == segunda.id
    assert len([r for r in sesion._responses if r.client_event_id == event_id]) == 1
    assert sesion.committed == 1  # solo el primer registro persiste


@pytest.mark.asyncio
async def test_presentacion_marca_ya_respondida() -> None:
    """Si el Usuario ya respondió, la presentación marca `already_answered`."""
    user_id = uuid.uuid4()
    path_id = uuid.uuid4()
    previa = SurveyResponse(
        id=uuid.uuid4(),
        profile_id=user_id,
        path_id=path_id,
        rating=5,
        answers={},
        geo_zone="zona-1",
        client_event_id=uuid.uuid4(),
    )
    sesion = _FakeSession(_survey(path_id), [previa])

    presentacion = await service.present_survey(sesion, path_id, user_id)

    assert presentacion.already_answered is True


@pytest.mark.asyncio
async def test_presentacion_sin_respuesta_previa() -> None:
    """Sin respuesta previa, la encuesta se presenta como no respondida."""
    user_id = uuid.uuid4()
    path_id = uuid.uuid4()
    sesion = _FakeSession(_survey(path_id), [])

    presentacion = await service.present_survey(sesion, path_id, user_id)

    assert presentacion.already_answered is False
    assert len(presentacion.questions) == 1
