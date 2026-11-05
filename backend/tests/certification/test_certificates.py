"""Pruebas del Certification Service: emisión, formato, idempotencia y acceso.

Feature: cima-plataforma.
- Property 19: emisión condicionada (ruta completa + evaluación aprobada) (Req 6.1, 6.2).
- Property 20: formato del código (16–64 alfanuméricos) y fecha ISO-8601 (Req 6.3).
- Property 21: idempotencia de emisión por (perfil, ruta) (Req 6.4).
- Property 22: autorización por titular en la consulta (Req 6.5, 6.6, 6.7).

Usan un stub de sesión async. El servicio invoca `scalar` en orden:
1) Certificado existente, 2) progreso de ruta, 3) intento aprobado. El stub
entrega esos resultados en secuencia.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest

from app.assessment.models import AssessmentAttempt
from app.certification import service
from app.certification.constants import CODE_MAX_LENGTH, CODE_MIN_LENGTH
from app.certification.models import Certificate
from app.common.errors import ForbiddenError, NotFoundError, ValidationError
from app.learning.models import PathProgress

_ALNUM = re.compile(r"^[A-Z0-9]+$")


class _IssueSession:
    """Stub para el flujo de emisión: `scalar` responde en el orden que llama el service.

    Secuencia esperada: (1) Certificado existente, (2) PathProgress, (3) intento
    aprobado. `add/commit/refresh` capturan el Certificado emitido y le asignan un
    `issued_at` como lo haría la BD.
    """

    def __init__(
        self,
        existing: Certificate | None,
        progress: PathProgress | None,
        passed_attempt: AssessmentAttempt | None,
    ) -> None:
        self._results = [existing, progress, passed_attempt]
        self._i = 0
        self.added: list[Certificate] = []

    async def scalar(self, _stmt):  # noqa: ANN201
        result = self._results[self._i] if self._i < len(self._results) else None
        self._i += 1
        return result

    def add(self, obj: Certificate) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: Certificate) -> None:
        if obj.issued_at is None:
            obj.issued_at = datetime.now(timezone.utc)


def _progress(profile_id: uuid.UUID, path_id: uuid.UUID, completed: bool) -> PathProgress:
    return PathProgress(
        id=uuid.uuid4(), profile_id=profile_id, path_id=path_id,
        completed_microcapsules=[], completed=completed, last_completed_step=0,
    )


def _passed(profile_id: uuid.UUID, path_id: uuid.UUID) -> AssessmentAttempt:
    return AssessmentAttempt(
        id=uuid.uuid4(), profile_id=profile_id, path_id=path_id,
        score=80, passed=True, attempt_number=1, cooldown_until=None,
    )


# --------------------------------------------------------------------------- #
# Property 19 — Emisión condicionada (Req 6.1, 6.2)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_19_emite_con_ruta_completa_y_aprobada() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, True), _passed(user, path))

    cert = await service.issue_certificate(session, user, path)

    assert cert.path_id == path
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_property_19_no_emite_si_ruta_incompleta() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, False), _passed(user, path))

    with pytest.raises(ValidationError):
        await service.issue_certificate(session, user, path)
    assert session.added == []


@pytest.mark.asyncio
async def test_property_19_no_emite_si_evaluacion_no_aprobada() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    # Ruta completa pero sin intento aprobado.
    session = _IssueSession(None, _progress(user, path, True), None)

    with pytest.raises(ValidationError):
        await service.issue_certificate(session, user, path)
    assert session.added == []


# --------------------------------------------------------------------------- #
# Property 20 — Formato del código y la fecha (Req 6.3)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_20_formato_codigo_y_fecha() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, True), _passed(user, path))

    cert = await service.issue_certificate(session, user, path)

    # Código alfanumérico con longitud en [16, 64] (Req 6.3).
    assert CODE_MIN_LENGTH <= len(cert.verification_code) <= CODE_MAX_LENGTH
    assert _ALNUM.match(cert.verification_code)
    # Fecha en ISO-8601 parseable.
    assert datetime.fromisoformat(cert.issued_at)


# --------------------------------------------------------------------------- #
# Property 21 — Idempotencia (Req 6.4)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_21_idempotencia_devuelve_el_existente() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    existing = Certificate(
        id=uuid.uuid4(), profile_id=user, path_id=path,
        verification_code="EXISTINGCODE1234567890", issued_at=datetime.now(timezone.utc),
    )
    session = _IssueSession(existing, _progress(user, path, True), _passed(user, path))

    cert = await service.issue_certificate(session, user, path)

    # Devuelve el existente y NO crea uno nuevo (Req 6.4, Property 21).
    assert cert.id == existing.id
    assert cert.verification_code == existing.verification_code
    assert session.added == []


# --------------------------------------------------------------------------- #
# Property 22 — Autorización por titular en la consulta (Req 6.5, 6.6, 6.7)
# --------------------------------------------------------------------------- #
class _GetSession:
    """Stub para la consulta: `get` devuelve el Certificado por id (o None)."""

    def __init__(self, certificate: Certificate | None) -> None:
        self._certificate = certificate

    async def get(self, _model, _pk) -> Certificate | None:
        return self._certificate


@pytest.mark.asyncio
async def test_property_22_titular_obtiene_su_certificado() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    cert = Certificate(
        id=uuid.uuid4(), profile_id=user, path_id=path,
        verification_code="CODE" + "A" * 16, issued_at=datetime.now(timezone.utc),
    )
    session = _GetSession(cert)

    result = await service.get_certificate(session, user, cert.id)
    assert result.id == cert.id


@pytest.mark.asyncio
async def test_property_22_recurso_ajeno_es_rechazado() -> None:
    owner, other, path = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    cert = Certificate(
        id=uuid.uuid4(), profile_id=owner, path_id=path,
        verification_code="CODE" + "B" * 16, issued_at=datetime.now(timezone.utc),
    )
    session = _GetSession(cert)

    # Otro usuario no puede ver el Certificado ajeno (anti-BOLA, Req 6.7).
    with pytest.raises(ForbiddenError):
        await service.get_certificate(session, other, cert.id)


@pytest.mark.asyncio
async def test_property_22_certificado_inexistente_no_encontrado() -> None:
    session = _GetSession(None)
    with pytest.raises(NotFoundError):
        await service.get_certificate(session, uuid.uuid4(), uuid.uuid4())
