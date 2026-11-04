"""Esquemas (DTO) del Conversion Service con validación estricta en servidor.

La entrada aplica allowlist de campos (`extra="forbid"`, rechaza claves
inesperadas) y tipado estricto (Zero Trust Input, Req 5.5). Las respuestas usan
DTOs con allowlist de campos y no exponen PII (Req 5.9); el `profile_id` nunca
viaja en el cuerpo de entrada: se toma del Usuario autenticado (anti-BOLA).
Requisitos: 5.4, 5.5, 5.8, 5.9.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, StrictStr


class MicroinsuranceOptionOut(BaseModel):
    """Opción de Microseguro presentada al Usuario (sin precio ni emisión)."""

    model_config = ConfigDict(frozen=True)

    codigo: str
    nombre: str
    descripcion: str


class MicroinsuranceOffer(BaseModel):
    """Oferta de Microseguros para una ruta: entre 1 y 5 opciones (Req 5.4)."""

    path_id: uuid.UUID
    activity_type: str
    options: list[MicroinsuranceOptionOut]


class ConversionIntentCreate(BaseModel):
    """Datos de entrada para registrar la intención de conversión (Req 5.5).

    No incluye `profile_id`: el titular se resuelve desde la cookie de sesión
    para no confiar en identificadores del cliente (anti-BOLA, Req 5.5).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_event_id: uuid.UUID
    option_code: StrictStr


class ConversionIntentResult(BaseModel):
    """DTO de salida tras registrar la intención; sin PII (Req 5.9)."""

    id: uuid.UUID
    path_id: uuid.UUID
    option_code: str
    registered: bool
