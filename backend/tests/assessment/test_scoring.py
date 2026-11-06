"""Pruebas del Assessment Service: puntaje, reintentos y validación.

Feature: cima-plataforma.
- Property 23: puntaje en [0, 100] y aprobado sii puntaje ≥ umbral (Req 7.2, 7.3).
- Property 24: ≤ 3 reintentos y enfriamiento de 24 h al agotarlos (Req 7.4, 7.5).
- Property 25: el puntaje se calcula sii la respuesta pasa la validación (Req 7.6, 7.7).

Usan un stub de sesión async que simula el subconjunto del ORM consumido por el
service (scalar, execute → scalars().all(), add, commit, refresh).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.assessment import service
from app.assessment.constants import COOLDOWN_HOURS, MAX_ATTEMPTS
from app.assessment.dto import AnswerItem, AnswerSubmission
from app.assessment.errors import EvaluacionYaAprobadaError, RutaNoCompletadaError
from app.assessment.models import Assessment, AssessmentAttempt
from app.common.errors import RateLimitedError, ValidationError
from app.learning.models import PathProgress

_NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _assessment(n_questions: int = 4, threshold: int = 70) -> Assessment:
    """Evaluación con `n` preguntas de 2 opciones; la opción correcta es 0."""
    questions = [
        {"id": i, "prompt": f"P{i}", "options": ["a", "b"], "correct": 0}
        for i in range(n_questions)
    ]
    return Assessment(id=uuid.uuid4(), path_id=uuid.uuid4(), questions=questions, pass_threshold=threshold)


class _ScalarsResult:
    def __init__(self, items: list[AssessmentAttempt]) -> None:
        self._items = items

    def scalars(self):  # noqa: ANN201
        return self

    def all(self) -> list[AssessmentAttempt]:
        return self._items


class _FakeSession:
    """Sesión async mínima: `scalar` devuelve la evaluación; `execute` los intentos."""

    def __init__(
        self,
        assessment: Assessment,
        previous: list[AssessmentAttempt] | None = None,
        path_completed: bool = True,
        has_progress: bool = True,
    ) -> None:
        self._assessment = assessment
        self._previous = previous or []
        self._path_completed = path_completed
        self._has_progress = has_progress
        self.added: list[AssessmentAttempt] = []

    async def scalar(self, stmt):  # noqa: ANN001, ANN201
        # El servicio consulta el progreso de la ruta (gate del Req 7.1) además de la
        # evaluación: se distingue por la tabla de la sentencia.
        if "path_progress" in str(stmt):
            if not self._has_progress:
                return None
            return PathProgress(
                id=uuid.uuid4(),
                profile_id=uuid.uuid4(),
                path_id=self._assessment.path_id,
                completed_microcapsules=[],
                completed=self._path_completed,
                last_completed_step=0,
            )
        return self._assessment

    async def execute(self, _stmt) -> _ScalarsResult:
        # Intentos ordenados del más reciente al más antiguo (como el service espera).
        ordered = sorted(self._previous, key=lambda a: a.created_at, reverse=True)
        return _ScalarsResult(ordered)

    def add(self, obj: AssessmentAttempt) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


def _full_answers(n: int, correct_count: int) -> AnswerSubmission:
    """Respuestas a `n` preguntas con `correct_count` aciertos (opción 0 = correcta)."""
    items = [
        AnswerItem(question_id=i, selected_option=0 if i < correct_count else 1)
        for i in range(n)
    ]
    return AnswerSubmission(answers=items)


# --------------------------------------------------------------------------- #
# Property 23 — Puntaje en [0, 100] y aprobación por umbral (Req 7.2, 7.3)
# --------------------------------------------------------------------------- #
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(n=st.integers(min_value=1, max_value=8), correct=st.integers(min_value=0, max_value=8))
@pytest.mark.asyncio
async def test_property_23_puntaje_en_rango_y_aprobacion(n: int, correct: int) -> None:
    """El puntaje queda en [0, 100] y se aprueba si y solo si alcanza el umbral."""
    correct = min(correct, n)
    assessment = _assessment(n_questions=n, threshold=70)
    session = _FakeSession(assessment)

    result = await service.submit_assessment(
        session, uuid.uuid4(), assessment.path_id, _full_answers(n, correct), now=_NOW
    )

    assert 0 <= result.score <= 100
    assert result.passed == (result.score >= assessment.pass_threshold)


# --------------------------------------------------------------------------- #
# Property 25 — Validación en servidor antes de calcular (Req 7.6, 7.7)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_25_respuesta_incompleta_se_rechaza_sin_puntaje() -> None:
    """Faltar preguntas por responder se rechaza sin calcular puntaje."""
    assessment = _assessment(n_questions=3)
    session = _FakeSession(assessment)
    # Solo 1 de 3 preguntas respondidas.
    submission = AnswerSubmission(answers=[AnswerItem(question_id=0, selected_option=0)])

    with pytest.raises(ValidationError):
        await service.submit_assessment(
            session, uuid.uuid4(), assessment.path_id, submission, now=_NOW
        )
    # No se registró ningún intento (no se calculó puntaje).
    assert session.added == []


@pytest.mark.asyncio
async def test_property_25_opcion_fuera_de_rango_se_rechaza() -> None:
    """Un índice de opción fuera del rango real se rechaza sin puntaje."""
    assessment = _assessment(n_questions=2)  # cada pregunta tiene 2 opciones (0,1)
    session = _FakeSession(assessment)
    submission = AnswerSubmission(
        answers=[
            AnswerItem(question_id=0, selected_option=0),
            AnswerItem(question_id=1, selected_option=5),  # fuera de rango
        ]
    )
    with pytest.raises(ValidationError):
        await service.submit_assessment(
            session, uuid.uuid4(), assessment.path_id, submission, now=_NOW
        )
    assert session.added == []


@pytest.mark.asyncio
async def test_property_25_pregunta_desconocida_se_rechaza() -> None:
    """Responder una pregunta inexistente se rechaza sin puntaje."""
    assessment = _assessment(n_questions=2)
    session = _FakeSession(assessment)
    submission = AnswerSubmission(
        answers=[
            AnswerItem(question_id=0, selected_option=0),
            AnswerItem(question_id=99, selected_option=0),  # no existe
        ]
    )
    with pytest.raises(ValidationError):
        await service.submit_assessment(
            session, uuid.uuid4(), assessment.path_id, submission, now=_NOW
        )
    assert session.added == []


# --------------------------------------------------------------------------- #
# Property 24 — Reintentos ≤ 3 y enfriamiento de 24 h (Req 7.4, 7.5)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_property_24_tercer_fallo_activa_enfriamiento() -> None:
    """Al agotar el 3.er intento no aprobado se activa enfriamiento de 24 h."""
    assessment = _assessment(n_questions=4, threshold=70)
    user = uuid.uuid4()
    # Dos intentos previos no aprobados en el ciclo vigente (sin cooldown).
    previous = [
        AssessmentAttempt(
            id=uuid.uuid4(), profile_id=user, path_id=assessment.path_id,
            score=0, passed=False, attempt_number=1, cooldown_until=None,
            created_at=_NOW - timedelta(minutes=10),
        ),
        AssessmentAttempt(
            id=uuid.uuid4(), profile_id=user, path_id=assessment.path_id,
            score=0, passed=False, attempt_number=2, cooldown_until=None,
            created_at=_NOW - timedelta(minutes=5),
        ),
    ]
    session = _FakeSession(assessment, previous)

    # Tercer intento, también reprobado (0 aciertos).
    result = await service.submit_assessment(
        session, user, assessment.path_id, _full_answers(4, 0), now=_NOW
    )

    assert result.attempt_number == MAX_ATTEMPTS
    assert result.passed is False
    assert result.attempts_remaining == 0
    assert result.cooldown_until is not None
    # La ventana de enfriamiento registrada es de 24 h.
    assert session.added[0].cooldown_until == _NOW + timedelta(hours=COOLDOWN_HOURS)


@pytest.mark.asyncio
async def test_property_24_enfriamiento_vigente_bloquea_nuevo_intento() -> None:
    """Con enfriamiento vigente, un nuevo intento se rechaza (429)."""
    assessment = _assessment(n_questions=4)
    user = uuid.uuid4()
    previous = [
        AssessmentAttempt(
            id=uuid.uuid4(), profile_id=user, path_id=assessment.path_id,
            score=0, passed=False, attempt_number=3,
            cooldown_until=_NOW + timedelta(hours=5),  # aún vigente
            created_at=_NOW - timedelta(hours=1),
        ),
    ]
    session = _FakeSession(assessment, previous)

    with pytest.raises(RateLimitedError):
        await service.submit_assessment(
            session, user, assessment.path_id, _full_answers(4, 4), now=_NOW
        )


@pytest.mark.asyncio
async def test_property_24_tras_enfriamiento_expirado_reinicia_contador() -> None:
    """Pasado el enfriamiento, el contador de intentos se reinicia (nuevo ciclo)."""
    assessment = _assessment(n_questions=4, threshold=70)
    user = uuid.uuid4()
    # Ciclo anterior cerrado con enfriamiento ya expirado.
    previous = [
        AssessmentAttempt(
            id=uuid.uuid4(), profile_id=user, path_id=assessment.path_id,
            score=0, passed=False, attempt_number=3,
            cooldown_until=_NOW - timedelta(hours=1),  # ya expiró
            created_at=_NOW - timedelta(hours=25),
        ),
    ]
    session = _FakeSession(assessment, previous)

    # Nuevo intento tras el enfriamiento: debe contar como el intento 1 del nuevo ciclo.
    result = await service.submit_assessment(
        session, user, assessment.path_id, _full_answers(4, 4), now=_NOW
    )
    assert result.attempt_number == 1
    assert result.passed is True


# --------------------------------------------------------------------------- #
# Req 7.1 — La evaluación exige la ruta completada
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_req_7_1_no_califica_si_la_ruta_no_esta_completa() -> None:
    """Sin ruta completada, calificar se rechaza (409) y no se registra ningún intento."""
    assessment = _assessment(n_questions=3)
    session = _FakeSession(assessment, path_completed=False)

    with pytest.raises(RutaNoCompletadaError):
        await service.submit_assessment(
            session, uuid.uuid4(), assessment.path_id, _full_answers(3, 3), now=_NOW
        )
    assert session.added == []


@pytest.mark.asyncio
async def test_req_7_1_no_califica_si_el_usuario_no_tiene_progreso() -> None:
    """Un Usuario que nunca empezó la ruta tampoco puede calificar."""
    assessment = _assessment(n_questions=3)
    session = _FakeSession(assessment, has_progress=False)

    with pytest.raises(RutaNoCompletadaError):
        await service.submit_assessment(
            session, uuid.uuid4(), assessment.path_id, _full_answers(3, 3), now=_NOW
        )
    assert session.added == []


@pytest.mark.asyncio
async def test_req_7_1_no_presenta_la_evaluacion_si_la_ruta_no_esta_completa() -> None:
    """Antes de terminar las lecciones, la evaluación no se entrega."""
    assessment = _assessment(n_questions=3)
    session = _FakeSession(assessment, path_completed=False)

    with pytest.raises(RutaNoCompletadaError):
        await service.get_assessment(session, uuid.uuid4(), assessment.path_id)


@pytest.mark.asyncio
async def test_req_7_1_presenta_la_evaluacion_sin_la_clave_si_la_ruta_esta_completa() -> None:
    """Con la ruta completa se presenta la evaluación, sin exponer la respuesta correcta."""
    assessment = _assessment(n_questions=3)
    session = _FakeSession(assessment, path_completed=True)

    result = await service.get_assessment(session, uuid.uuid4(), assessment.path_id)

    assert len(result.questions) == 3
    assert "correct" not in result.model_dump_json()


# --------------------------------------------------------------------------- #
# Req 7.3 — Una evaluación aprobada no se vuelve a calificar
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_req_7_3_no_recalifica_una_evaluacion_ya_aprobada() -> None:
    """Tras aprobar, un nuevo envío se rechaza (409) y no registra otro intento."""
    assessment = _assessment(n_questions=4, threshold=70)
    user = uuid.uuid4()
    previous = [
        AssessmentAttempt(
            id=uuid.uuid4(), profile_id=user, path_id=assessment.path_id,
            score=100, passed=True, attempt_number=1, cooldown_until=None,
            created_at=_NOW - timedelta(minutes=5),
        ),
    ]
    session = _FakeSession(assessment, previous)

    with pytest.raises(EvaluacionYaAprobadaError):
        await service.submit_assessment(
            session, user, assessment.path_id, _full_answers(4, 4), now=_NOW
        )
    assert session.added == []
