"""Esquemas (DTO) del Certification Service con validación estricta en servidor.

Aplica allowlist de campos (`extra="forbid"`). La respuesta expone solo los
campos autorizados del Certificado (nunca el objeto ORM completo ni el
`profile_id` del titular), con la fecha en ISO-8601 (Req 6.3, 9.5).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class IssueCertificateRequest(BaseModel):
    """Solicitud de emisión de Certificado para una ruta completada.

    `extra="forbid"` implementa la allowlist de campos (Zero Trust Input). El
    titular no se envía en el cuerpo: se toma de la identidad autenticada
    (anti-BOLA, Req 6.5).
    """

    model_config = ConfigDict(extra="forbid")

    path_id: uuid.UUID


class CertificateResponse(BaseModel):
    """DTO de salida de un Certificado (allowlist de campos, sin PII, Req 9.5).

    Expone el identificador del Certificado, la ruta, el código verificable y la
    fecha de emisión en ISO-8601; no incluye el `profile_id` del titular.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    path_id: uuid.UUID
    verification_code: str
    issued_at: str
