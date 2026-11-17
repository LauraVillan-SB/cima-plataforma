"""Esquemas (DTO) del Certification Service con validación estricta en servidor.

Aplica allowlist de campos (`extra="forbid"`). La respuesta expone solo los
campos autorizados del Certificado (nunca el objeto ORM completo ni el
`profile_id` del titular), con la fecha en ISO-8601 (Req 6.3, 9.5).
"""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.common.masking import DEFAULT_VISIBLE_CHARS as MAX_VISIBLES


class IssueCertificateRequest(BaseModel):
    """Solicitud de emisión de Certificado para una ruta completada.

    `extra="forbid"` implementa la allowlist de campos (Zero Trust Input). El
    titular no se envía en el cuerpo: se toma de la identidad autenticada
    (anti-BOLA, Req 6.5).
    """

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID


class CertificateResponse(BaseModel):
    """DTO de salida de un Certificado (allowlist de campos, Req 6.3, 9.4, 9.5).

    Expone el identificador del Certificado, la ruta, el código verificable y la
    fecha de emisión en ISO-8601. Para mostrarlo en pantalla trae además el nombre de
    la ruta y el celular del titular **enmascarado** (como máximo los últimos 4
    caracteres visibles, Req 9.4). Nunca incluye el `profile_id` ni el celular completo.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    path_id: uuid.UUID
    verification_code: str
    issued_at: str
    path_title: Optional[str] = None
    holder_phone_masked: Optional[str] = None

    @field_validator("holder_phone_masked")
    @classmethod
    def _solo_enmascarado(cls, value: Optional[str]) -> Optional[str]:
        """Defensa en profundidad: rechaza un celular con más de 4 caracteres a la vista."""
        if value is not None and len(value.lstrip("*")) > MAX_VISIBLES:
            raise ValueError("El celular del titular debe ir enmascarado.")
        return value
