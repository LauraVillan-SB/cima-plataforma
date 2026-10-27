"""Pruebas del Profile Service y la infraestructura transversal.

Incluye pruebas unitarias y basadas en propiedades (Hypothesis) que validan:
- Enmascaramiento de PII (Property 18).
- Allowlist de campos y validación del Perfil (Properties 30, 31).
- Autorización por propiedad del recurso / anti-BOLA (Property 22).

Feature: cima-plataforma
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.common.masking import mask_value
from app.profile.constants import ALLOWED_ACTIVITY_TYPES, GEO_ZONE_MAX_LENGTH
from app.profile.dto import ProfileCreate


# --------------------------------------------------------------------------- #
# Property 18 — Enmascaramiento de PII (Req 5.9, 9.4)
# --------------------------------------------------------------------------- #
@given(value=st.text(min_size=0, max_size=40), visible=st.integers(min_value=0, max_value=10))
def test_mask_value_nunca_revela_mas_de_lo_permitido(value: str, visible: int) -> None:
    # When
    masked = mask_value(value, visible)
    # Then: la longitud se conserva y no hay más caracteres visibles que `visible`.
    assert len(masked) == len(value)
    visibles = min(visible, len(value))
    assert masked.endswith(value[len(value) - visibles:]) if visibles else True
    assert masked[: len(value) - visibles] == "*" * (len(value) - visibles)


def test_mask_value_ejemplo_telefono() -> None:
    # Given/When/Then
    assert mask_value("3001234567") == "******4567"


# --------------------------------------------------------------------------- #
# Property 30 — Allowlist de campos del Perfil (Req 9.1)
# --------------------------------------------------------------------------- #
def test_perfil_rechaza_campos_no_permitidos() -> None:
    # Given un payload con un campo extra no permitido
    payload = {
        "phone": "3001234567",
        "activity_type": "cafe",
        "geo_zone": "Huila",
        "cedula": "123456789",  # campo no permitido
    }
    # When / Then: la validación falla (allowlist estricta)
    with pytest.raises(PydanticValidationError):
        ProfileCreate(**payload)


# --------------------------------------------------------------------------- #
# Property 31 — Normalización y validación del Perfil (Req 9.2, 9.3)
# --------------------------------------------------------------------------- #
@given(
    activity=st.sampled_from(sorted(ALLOWED_ACTIVITY_TYPES)),
    digits=st.integers(min_value=7, max_value=15),
)
def test_perfil_valido_se_acepta_y_normaliza(activity: str, digits: int) -> None:
    # Given un teléfono con dígitos válidos y espacios alrededor de la zona
    phone = "3" * digits
    # When
    dto = ProfileCreate(phone=phone, activity_type=activity.upper(), geo_zone="  Huila  ")
    # Then: el tipo se normaliza a minúsculas y la zona se recorta (trim)
    assert dto.activity_type == activity
    assert dto.geo_zone == "Huila"


@given(digits=st.integers(min_value=0, max_value=6))
def test_perfil_rechaza_telefono_corto(digits: int) -> None:
    # Given un teléfono con menos de 7 dígitos
    with pytest.raises(PydanticValidationError):
        ProfileCreate(phone="3" * digits, activity_type="cafe", geo_zone="Huila")


def test_perfil_rechaza_actividad_fuera_de_allowlist() -> None:
    with pytest.raises(PydanticValidationError):
        ProfileCreate(phone="3001234567", activity_type="mineria", geo_zone="Huila")


def test_perfil_rechaza_zona_demasiado_larga() -> None:
    with pytest.raises(PydanticValidationError):
        ProfileCreate(
            phone="3001234567",
            activity_type="cafe",
            geo_zone="z" * (GEO_ZONE_MAX_LENGTH + 1),
        )


# --------------------------------------------------------------------------- #
# Property 22 — Autorización por propiedad del recurso (anti-BOLA, Req 9.6)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_actualizar_perfil_ajeno_es_rechazado() -> None:
    from app.common.errors import ForbiddenError
    from app.profile import service

    # Given dos identidades distintas
    current_user = uuid.uuid4()
    otro_perfil = uuid.uuid4()
    data = ProfileCreate(phone="3001234567", activity_type="cafe", geo_zone="Huila")

    # When / Then: intentar modificar un perfil ajeno lanza ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.update_own_profile(
            db=None, current_user_id=current_user, target_id=otro_perfil, data=data
        )
