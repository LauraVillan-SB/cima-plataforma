"""Pruebas de propiedad de la validación en servidor de la respuesta de encuesta.

Feature: cima-plataforma, Property 43: Validación en servidor de la respuesta
de encuesta.
Validates: Requirements 20.3

La validación es pura (Pydantic), así que no requiere BD. Se verifica que la
calificación fuera del rango 1–5, las claves inesperadas y los tipos inválidos
se rechacen antes de cualquier registro.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.survey.constants import RATING_MAX, RATING_MIN
from app.survey.dto import SurveyResponseCreate


def _payload(**overrides) -> dict:
    base = {
        "client_event_id": str(uuid.uuid4()),
        "profile_id": str(uuid.uuid4()),
        "rating": 3,
        "answers": {},
    }
    base.update(overrides)
    return base


# Feature: cima-plataforma, Property 43: Validación en servidor de la respuesta.
# Validates: Requirements 20.3
@settings(max_examples=100, deadline=None)
@given(rating=st.integers(min_value=-50, max_value=50))
def test_property_43_rating_dentro_de_rango(rating: int) -> None:
    """La calificación se acepta si y solo si está en [RATING_MIN, RATING_MAX]."""
    payload = _payload(rating=rating)
    if RATING_MIN <= rating <= RATING_MAX:
        dto = SurveyResponseCreate(**payload)
        assert dto.rating == rating
    else:
        with pytest.raises(PydanticValidationError):
            SurveyResponseCreate(**payload)


@settings(max_examples=100, deadline=None)
@given(
    clave=st.text(min_size=1, max_size=20).filter(
        lambda s: s not in {"client_event_id", "profile_id", "rating", "answers", "geo_zone"}
    )
)
def test_property_43_rechaza_claves_inesperadas(clave: str) -> None:
    """Cualquier clave fuera de la allowlist hace fallar la validación (extra=forbid)."""
    payload = _payload(**{clave: "x"})
    with pytest.raises(PydanticValidationError):
        SurveyResponseCreate(**payload)


def test_rating_tipo_invalido_se_rechaza() -> None:
    """Un tipo no entero para la calificación se rechaza sin registrar."""
    with pytest.raises(PydanticValidationError):
        SurveyResponseCreate(**_payload(rating="cinco"))


def test_geo_zone_excede_maximo_se_rechaza() -> None:
    """Una zona más larga que el máximo permitido se rechaza."""
    with pytest.raises(PydanticValidationError):
        SurveyResponseCreate(**_payload(geo_zone="z" * 200))
