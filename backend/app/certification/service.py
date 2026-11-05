"""Lógica de negocio del Certification Service.

Cubre la emisión condicionada de Certificados (Req 6.1, 6.2) de forma idempotente
por (perfil, ruta) (Req 6.4), con código verificable y fecha ISO-8601 (Req 6.3),
y la consulta con autorización por titular (Req 6.5, 6.6, 6.7).

La emisión exige dos condiciones verificadas en el servidor:
1. La Ruta_de_Aprendizaje está completa para el Usuario (Learning, Req 4.10).
2. La evaluación de la ruta fue aprobada por el Usuario (Assessment, Req 6.1).

Principios aplicados:
- Consultas parametrizadas vía ORM; nunca SQL concatenado.
- Autorización por propiedad: emisión y consulta se anclan al `current_user_id`
  de la sesión; nunca se confía en un id del cliente (anti-BOLA, Req 9.6).
- Idempotencia por restricción UNIQUE(profile_id, path_id) (Req 6.4).
- Errores de dominio específicos; sin `except` genérico en la lógica.
- Logs estructurados sin PII (Req 9.4).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.models import AssessmentAttempt
from app.certification.constants import generate_verification_code
from app.certification.dto import CertificateResponse
from app.certification.models import Certificate
from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.common.logging import log_event
from app.learning.models import PathProgress

logger = logging.getLogger("cima.certification")


def _to_response(certificate: Certificate) -> CertificateResponse:
    """Construye el DTO de salida con la fecha en ISO-8601 (Req 6.3, 9.5)."""
    return CertificateResponse(
        id=certificate.id,
        path_id=certificate.path_id,
        verification_code=certificate.verification_code,
        issued_at=certificate.issued_at.isoformat(),
    )


async def _path_completed(
    db: AsyncSession, profile_id: uuid.UUID, path_id: uuid.UUID
) -> bool:
    """Indica si la ruta está completa para el Usuario (Learning, Req 4.10)."""
    progress = await db.scalar(
        select(PathProgress).where(
            PathProgress.profile_id == profile_id,
            PathProgress.path_id == path_id,
        )
    )
    return bool(progress and progress.completed)


async def _assessment_passed(
    db: AsyncSession, profile_id: uuid.UUID, path_id: uuid.UUID
) -> bool:
    """Indica si el Usuario aprobó la evaluación de la ruta (Assessment, Req 6.1)."""
    passed_attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.profile_id == profile_id,
            AssessmentAttempt.path_id == path_id,
            AssessmentAttempt.passed.is_(True),
        )
    )
    return passed_attempt is not None


async def issue_certificate(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> CertificateResponse:
    """Emite el Certificado de una ruta para el Usuario autenticado.

    Idempotente: si ya existe un Certificado para (perfil, ruta) se devuelve el
    existente sin crear otro (Req 6.4, Property 21). La emisión solo procede si la
    ruta está completa y la evaluación fue aprobada (Req 6.1); de lo contrario se
    rechaza sin emitir (Req 6.2, Property 19).
    """
    existing = await db.scalar(
        select(Certificate).where(
            Certificate.profile_id == current_user_id,
            Certificate.path_id == path_id,
        )
    )
    if existing is not None:
        log_event(logger, "certificate_idempotent_hit", certificate_id=str(existing.id))
        return _to_response(existing)

    if not await _path_completed(db, current_user_id, path_id):
        raise ValidationError(internal_detail="path not completed")
    if not await _assessment_passed(db, current_user_id, path_id):
        # No se alcanzó el puntaje mínimo de aprobación (Req 6.2).
        raise ValidationError(internal_detail="assessment not passed")

    certificate = Certificate(
        profile_id=current_user_id,
        path_id=path_id,
        verification_code=generate_verification_code(),
    )
    db.add(certificate)
    await db.commit()
    await db.refresh(certificate)
    log_event(logger, "certificate_issued", certificate_id=str(certificate.id))
    return _to_response(certificate)


async def get_certificate(
    db: AsyncSession, current_user_id: uuid.UUID, certificate_id: uuid.UUID
) -> CertificateResponse:
    """Devuelve un Certificado solo si el solicitante es su titular (Req 6.5–6.7).

    - Inexistente → NotFoundError, sin revelar información de otros Perfiles (Req 6.6).
    - De otro titular → ForbiddenError y registro del intento sin PII (Req 6.7),
      sin revelar el contenido del Certificado.
    """
    certificate = await db.get(Certificate, certificate_id)
    if certificate is None:
        raise NotFoundError(internal_detail=f"certificate {certificate_id} not found")

    if certificate.profile_id != current_user_id:
        log_event(
            logger,
            "certificate_access_denied",
            actor_id=str(current_user_id),
            certificate_id=str(certificate_id),
        )
        raise ForbiddenError(internal_detail="cross-user certificate access blocked")

    return _to_response(certificate)
