"""DTOs del dominio de autenticación (allowlist, validación estricta en servidor).

Define la validación de la Clave de 4 dígitos (Req 1.4) y el DTO de registro
con doble confirmación de Clave (Req 1.3). La validación ocurre en servidor con
Pydantic; el teléfono se valida en formato E.164 reducido (7-15 dígitos, Req 1.1).
"""
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

# Clave: exactamente 4 dígitos numéricos (Req 1.4 / Property 1).
Clave = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]

# Teléfono: solo dígitos, longitud 7-15 (E.164 reducido, Req 1.1 / Req 9.2).
Telefono = Annotated[str, StringConstraints(pattern=r"^\d{7,15}$")]


class RegistroRequest(BaseModel):
    """Solicitud de registro: teléfono + Clave con doble confirmación.

    Rechaza claves no permitidas (allowlist, `extra='forbid'`) y exige que la
    Clave y su confirmación coincidan exactamente (Req 1.3, 1.4).
    """

    model_config = {"extra": "forbid"}

    telefono: Telefono
    clave: Clave
    confirmacion_clave: Clave

    @model_validator(mode="after")
    def claves_coinciden(self) -> "RegistroRequest":
        """Valida que la Clave y su confirmación sean idénticas (doble confirmación)."""
        if self.clave != self.confirmacion_clave:
            raise ValueError("La Clave y su confirmación no coinciden")
        return self


class IngresoRequest(BaseModel):
    """Solicitud de ingreso: teléfono + Clave de 4 dígitos (Req 1.6)."""

    model_config = {"extra": "forbid"}

    telefono: Telefono
    clave: Clave


class CambioClaveRequest(BaseModel):
    """Cambio de Clave: exige la Clave actual y la nueva (Req 1.14)."""

    model_config = {"extra": "forbid"}

    clave_actual: Clave
    clave_nueva: Clave
    confirmacion_clave_nueva: Clave

    @model_validator(mode="after")
    def nuevas_coinciden(self) -> "CambioClaveRequest":
        """Valida que la nueva Clave y su confirmación coincidan."""
        if self.clave_nueva != self.confirmacion_clave_nueva:
            raise ValueError("La nueva Clave y su confirmación no coinciden")
        return self
