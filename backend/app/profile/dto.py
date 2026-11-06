"""Esquemas (DTO) del Perfil de Usuario con validación estricta en servidor.

Aplica allowlist de campos (rechaza claves inesperadas), normalización (trim) y
validación de tipo, formato, longitud y rango (Req 9.1, 9.2, 9.3). La respuesta
expone solo los campos autorizados, con la PII enmascarada (Req 9.4, 9.5).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.profile.constants import (
    ALLOWED_ACTIVITY_TYPES,
    GEO_ZONE_MAX_LENGTH,
    PHONE_MAX_DIGITS,
    PHONE_MIN_DIGITS,
)


def _normalizar_actividad(value: str) -> str:
    """Valida que el tipo de actividad pertenezca a la allowlist (Req 9.2)."""
    normalized = value.lower()
    if normalized not in ALLOWED_ACTIVITY_TYPES:
        raise ValueError("El tipo de cultivo o comercio no está en la lista permitida.")
    return normalized


def _validar_zona(value: str) -> str:
    """Valida que la zona no esté vacía ni exceda 100 caracteres (Req 9.2)."""
    if not value:
        raise ValueError("La zona geográfica es obligatoria.")
    if len(value) > GEO_ZONE_MAX_LENGTH:
        raise ValueError(f"La zona geográfica no puede exceder {GEO_ZONE_MAX_LENGTH} caracteres.")
    return value


class ProfileCreate(BaseModel):
    """Datos de entrada para crear un Perfil.

    `extra="forbid"` implementa la allowlist de campos: cualquier clave no
    declarada hace fallar la validación (Req 9.1).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phone: str
    activity_type: str
    geo_zone: str

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        """Valida que el teléfono tenga entre 7 y 15 dígitos numéricos (Req 9.2)."""
        digits = value.lstrip("+")
        if not digits.isdigit() or not (PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS):
            raise ValueError(
                f"El teléfono debe tener entre {PHONE_MIN_DIGITS} y {PHONE_MAX_DIGITS} dígitos."
            )
        return value

    @field_validator("activity_type")
    @classmethod
    def _validate_activity(cls, value: str) -> str:
        """Valida que el tipo de actividad pertenezca a la allowlist (Req 9.2)."""
        return _normalizar_actividad(value)

    @field_validator("geo_zone")
    @classmethod
    def _validate_geo_zone(cls, value: str) -> str:
        """Valida que la zona no esté vacía ni exceda 100 caracteres (Req 9.2)."""
        return _validar_zona(value)


class ProfileUpdate(BaseModel):
    """Datos de entrada para actualizar el Perfil propio.

    Solo admite el tipo de cultivo o comercio y la zona. El teléfono NO es
    editable por esta vía: es la identidad con la que la persona entra y se fija
    al registrarse. Además, el cliente nunca lo conoce completo (la respuesta lo
    entrega enmascarado, Req 9.4), así que exigirlo aquí hacía fallar toda
    actualización. `extra="forbid"` mantiene la allowlist estricta (Req 9.1): un
    `phone` en el cuerpo se rechaza.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    activity_type: str
    geo_zone: str

    @field_validator("activity_type")
    @classmethod
    def _validate_activity(cls, value: str) -> str:
        """Valida que el tipo de actividad pertenezca a la allowlist (Req 9.2)."""
        return _normalizar_actividad(value)

    @field_validator("geo_zone")
    @classmethod
    def _validate_geo_zone(cls, value: str) -> str:
        """Valida que la zona no esté vacía ni exceda 100 caracteres (Req 9.2)."""
        return _validar_zona(value)


class ProfileResponse(BaseModel):
    """DTO de salida con allowlist de campos y PII enmascarada (Req 9.4, 9.5)."""

    id: uuid.UUID
    phone: str  # Enmascarado por el servicio antes de construir el DTO.
    activity_type: str
    geo_zone: str
