"""Pruebas del Certification Service: emisión, formato, idempotencia y acceso.

Feature: cima-plataforma.
- Property 19: emisión condicionada (ruta completa + evaluación aprobada) (Req 6.1, 6.2).
- Property 20: formato del código (16–64 alfanuméricos) y fecha ISO-8601 (Req 6.3).
- Property 21: idempotencia de emisión por (perfil, ruta) (Req 6.4).
- Property 22: autorización por titular en la consulta (Req 6.5, 6.6, 6.7).
- Contenido para la pantalla: nombre de la ruta y celular del titular enmascarado
  (Req 9.4), y mensajes claros cuando aún no se puede emitir (Req 6.2).

Usan un stub de sesión async. El servicio invoca `scalar` en orden:
1) Certificado existente, 2) progreso de ruta, 3) intento aprobado. `get` responde por
modelo: la ruta, el Perfil o el Certificado.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.assessment.models import AssessmentAttempt
from app.certification import service
from app.certification.constants import CODE_MAX_LENGTH, CODE_MIN_LENGTH
from app.certification.dto import CertificateResponse
from app.certification.errors import (
    EvaluacionNoAprobadaError,
    RutaNoCompletadaParaCertificadoError,
)
from app.certification.models import Certificate
from app.common.database import get_session
from app.common.errors import ForbiddenError, NotFoundError
from app.common.masking import mask_value
from app.common.security import get_current_user_id
from app.learning.models import LearningPath, PathProgress
from app.main import app
from app.profile.models import Profile

_ALNUM = re.compile(r"^[A-Z0-9]+$")
# Valores ficticios: no son datos reales.
_CELULAR = "+573001234567"
_TITULO = "Ruta del cafetal"


def _ruta(path_id: uuid.UUID, titulo: str | None = _TITULO) -> LearningPath:
    return LearningPath(id=path_id, microcapsule_ids=[], pass_threshold=70, title=titulo)


def _perfil(profile_id: uuid.UUID, celular: str = _CELULAR) -> Profile:
    return Profile(id=profile_id, phone_e164=celular)


class _IssueSession:
    """Stub para el flujo de emisión: `scalar` responde en el orden que llama el service.

    Secuencia esperada: (1) Certificado existente, (2) PathProgress, (3) intento
    aprobado. `get` devuelve la ruta y el Perfil. `add/commit/refresh` capturan el
    Certificado emitido y le asignan un `issued_at` como lo haría la BD.
    """

    def __init__(
        self,
        existing: Certificate | None,
        progress: PathProgress | None,
        passed_attempt: AssessmentAttempt | None,
        ruta: LearningPath | None = None,
        perfil: Profile | None = None,
    ) -> None:
        self._results = [existing, progress, passed_attempt]
        self._i = 0
        self._por_modelo = {LearningPath: ruta, Profile: perfil}
        self.added: list[Certificate] = []

    async def scalar(self, _stmt):  # noqa: ANN201
        result = self._results[self._i] if self._i < len(self._results) else None
        self._i += 1
        return result

    async def get(self, model, _pk):  # noqa: ANN001, ANN201
        return self._por_modelo.get(model)

    def add(self, obj: Certificate) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: Certificate) -> None:
        # Simula la asignación de PK y timestamp por la BD tras el flush/commit.
        if obj.id is None:
            obj.id = uuid.uuid4()
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

    with pytest.raises(RutaNoCompletadaParaCertificadoError):
        await service.issue_certificate(session, user, path)
    assert session.added == []


@pytest.mark.asyncio
async def test_property_19_no_emite_si_evaluacion_no_aprobada() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    # Ruta completa pero sin intento aprobado.
    session = _IssueSession(None, _progress(user, path, True), None)

    with pytest.raises(EvaluacionNoAprobadaError):
        await service.issue_certificate(session, user, path)
    assert session.added == []


def test_el_mensaje_de_no_aprobada_dice_que_falta_el_puntaje_minimo() -> None:
    """Req 6.2: el mensaje indica que no se alcanzó el puntaje mínimo."""
    assert "puntaje mínimo" in EvaluacionNoAprobadaError.public_message
    assert EvaluacionNoAprobadaError.status_code == 409
    assert RutaNoCompletadaParaCertificadoError.status_code == 409


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
# Contenido para la pantalla (Req 9.4)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_la_respuesta_trae_la_ruta_y_el_celular_enmascarado() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(
        None, _progress(user, path, True), _passed(user, path), _ruta(path), _perfil(user)
    )

    cert = await service.issue_certificate(session, user, path)

    assert cert.path_title == _TITULO
    assert cert.holder_phone_masked == "*********4567"
    assert _CELULAR not in cert.model_dump_json()
    assert str(user) not in cert.model_dump_json()


@pytest.mark.asyncio
async def test_sin_ruta_ni_perfil_la_respuesta_queda_sin_esos_datos() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, True), _passed(user, path))

    cert = await service.issue_certificate(session, user, path)

    assert cert.path_title is None
    assert cert.holder_phone_masked is None


@settings(max_examples=200, deadline=None)
@given(celular=st.text(alphabet="+0123456789", min_size=1, max_size=16))
def test_el_celular_nunca_sale_con_mas_de_4_caracteres_visibles(celular: str) -> None:
    respuesta = CertificateResponse(
        id=uuid.uuid4(), path_id=uuid.uuid4(), verification_code="A" * 32,
        issued_at="2026-11-14T00:00:00+00:00", holder_phone_masked=mask_value(celular),
    )

    assert len(respuesta.holder_phone_masked.lstrip("*")) <= 4


@pytest.mark.parametrize("sin_enmascarar", ["+573001234567", "3001234567", "12345"])
def test_el_dto_rechaza_un_celular_sin_enmascarar(sin_enmascarar: str) -> None:
    with pytest.raises(PydanticValidationError):
        CertificateResponse(
            id=uuid.uuid4(), path_id=uuid.uuid4(), verification_code="A" * 32,
            issued_at="2026-11-14T00:00:00+00:00", holder_phone_masked=sin_enmascarar,
        )


# --------------------------------------------------------------------------- #
# Property 22 — Autorización por titular en la consulta (Req 6.5, 6.6, 6.7)
# --------------------------------------------------------------------------- #
class _GetSession:
    """Stub para la consulta: `get` responde por modelo (Certificado, ruta o Perfil)."""

    def __init__(self, certificate: Certificate | None, perfil: Profile | None = None) -> None:
        self._por_modelo = {Certificate: certificate, LearningPath: None, Profile: perfil}
        self.perfiles_leidos = 0

    async def get(self, model, _pk):  # noqa: ANN001, ANN201
        if model is Profile:
            self.perfiles_leidos += 1
        return self._por_modelo.get(model)


@pytest.mark.asyncio
async def test_property_22_titular_obtiene_su_certificado() -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    cert = Certificate(
        id=uuid.uuid4(), profile_id=user, path_id=path,
        verification_code="CODE" + "A" * 16, issued_at=datetime.now(timezone.utc),
    )
    session = _GetSession(cert, _perfil(user))

    result = await service.get_certificate(session, user, cert.id)
    assert result.id == cert.id
    assert result.holder_phone_masked == "*********4567"


@pytest.mark.asyncio
async def test_property_22_recurso_ajeno_es_rechazado() -> None:
    owner, other, path = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    cert = Certificate(
        id=uuid.uuid4(), profile_id=owner, path_id=path,
        verification_code="CODE" + "B" * 16, issued_at=datetime.now(timezone.utc),
    )
    session = _GetSession(cert, _perfil(owner))

    # Otro usuario no puede ver el Certificado ajeno (anti-BOLA, Req 6.7).
    with pytest.raises(ForbiddenError):
        await service.get_certificate(session, other, cert.id)
    # Ni siquiera se lee el Perfil del titular: no se arma ningún dato suyo.
    assert session.perfiles_leidos == 0


@pytest.mark.asyncio
async def test_property_22_certificado_inexistente_no_encontrado() -> None:
    session = _GetSession(None)
    with pytest.raises(NotFoundError):
        await service.get_certificate(session, uuid.uuid4(), uuid.uuid4())


# --------------------------------------------------------------------------- #
# Endpoint (respuesta HTTP que ve el Usuario)
# --------------------------------------------------------------------------- #
def _post(user: uuid.UUID, session: object, cuerpo: dict) -> object:
    """POST /api/v1/certificados con sesión de Usuario y de BD simuladas."""

    async def _sesion():  # noqa: ANN202
        yield session

    app.dependency_overrides[get_current_user_id] = lambda: user
    app.dependency_overrides[get_session] = _sesion
    try:
        return TestClient(app).post("/api/v1/certificados", json=cuerpo)
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize(
    ("completa", "fragmento"),
    [(False, "termine todas las lecciones"), (True, "puntaje mínimo")],
)
def test_el_endpoint_responde_409_con_un_mensaje_claro(completa: bool, fragmento: str) -> None:
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, completa), None)

    respuesta = _post(user, session, {"path_id": str(path)})

    assert respuesta.status_code == 409
    assert fragmento in respuesta.json()["detail"]
    assert session.added == []


def test_el_endpoint_rechaza_campos_extra_como_el_titular() -> None:
    """El titular sale de la sesión; un `profile_id` en el cuerpo se rechaza (anti-BOLA)."""
    user, path = uuid.uuid4(), uuid.uuid4()
    session = _IssueSession(None, _progress(user, path, True), _passed(user, path))

    respuesta = _post(user, session, {"path_id": str(path), "profile_id": str(uuid.uuid4())})

    assert respuesta.status_code == 422
    assert session.added == []
