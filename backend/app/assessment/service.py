"""Lógica de negocio del Assessment Service.

Cubre la presentación de la evaluación (Req 7.1), la validación en servidor de
las respuestas antes de calcular (Req 7.6, 7.7, Property 25), el cálculo de
puntaje 0–100 con marcado de aprobado según umbral (Req 7.2, 7.3, Property 23) y
el control de reintentos (≤ 3) con enfriamiento de 24 h (Req 7.4, 7.5,
Property 24).

Principios aplicados:
- Consultas parametrizadas vía ORM; nunca SQL concatenado.
- Autorización por propiedad: los intentos se anclan al `current_user_id` de la
  sesión; nunca se confía en un id del cliente (anti-BOLA, Req 9.6).
- La clave de respuestas y el cálculo viven solo en el servidor (Req 7.6).
- Errores de dominio específicos; sin `except` genérico en la lógica.
- Logs estructurados sin PII (Req 9.4).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.constants import (
    COOLDOWN_HOURS,
    MAX_ATTEMPTS,
    MAX_SCORE,
    MIN_SCORE,
)
from app.assessment.dto import (
    AnswerSubmission,
    AssessmentOut,
    AttemptResult,
    QuestionOut,
)
from app.assessment.errors import EvaluacionYaAprobadaError, RutaNoCompletadaError
from app.assessment.models import Assessment, AssessmentAttempt
from app.common.errors import NotFoundError, RateLimitedError, ValidationError
from app.common.logging import log_event
from app.learning.models import PathProgress

logger = logging.getLogger("cima.assessment")


async def _require_path_completed(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> None:
    """Exige que el Usuario haya terminado todas las lecciones de la ruta (Req 7.1).

    Lee el progreso del Learning Service anclado al `current_user_id` autenticado
    (anti-BOLA); nunca confía en un id del cliente. Sin progreso o con la ruta sin
    completar, lanza `RutaNoCompletadaError` (409) sin revelar el contenido.
    """
    progress = await db.scalar(
        select(PathProgress).where(
            PathProgress.profile_id == current_user_id,
            PathProgress.path_id == path_id,
        )
    )
    if progress is None or not progress.completed:
        log_event(logger, "assessment_blocked_path_incomplete")
        raise RutaNoCompletadaError(internal_detail="path not completed by user")


async def _get_assessment(db: AsyncSession, path_id: uuid.UUID) -> Assessment:
    """Recupera la evaluación de una ruta o lanza NotFoundError (consulta parametrizada)."""
    assessment = await db.scalar(
        select(Assessment).where(Assessment.path_id == path_id)
    )
    if assessment is None:
        raise NotFoundError(internal_detail=f"assessment for path {path_id} not found")
    return assessment


async def get_assessment(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> AssessmentOut:
    """Presenta la evaluación de una ruta sin revelar la clave de respuestas.

    Solo se presenta cuando el Usuario terminó todas las lecciones de la ruta
    (Req 7.1); antes, responde 409 sin entregar preguntas.
    """
    assessment = await _get_assessment(db, path_id)
    await _require_path_completed(db, current_user_id, path_id)
    questions = [
        QuestionOut(id=q["id"], prompt=q["prompt"], options=list(q["options"]))
        for q in assessment.questions
    ]
    log_event(logger, "assessment_presented", question_count=len(questions))
    return AssessmentOut(path_id=path_id, questions=questions)


def _validate_answers(assessment: Assessment, submission: AnswerSubmission) -> dict[int, int]:
    """Valida las respuestas contra la definición antes de calcular (Req 7.6, 7.7).

    Comprueba que cada respuesta refiera a una pregunta existente, que el índice
    de opción esté dentro del rango real de opciones, y que se responda cada
    pregunta exactamente una vez (sin faltantes ni duplicados). Devuelve el mapa
    {question_id: selected_option} si es válido; si no, lanza ValidationError sin
    calcular puntaje (Property 25).
    """
    questions_by_id = {q["id"]: q for q in assessment.questions}
    answered: dict[int, int] = {}

    for item in submission.answers:
        question = questions_by_id.get(item.question_id)
        if question is None:
            raise ValidationError(internal_detail=f"unknown question {item.question_id}")
        if item.question_id in answered:
            raise ValidationError(
                internal_detail=f"duplicate answer for question {item.question_id}"
            )
        if not (0 <= item.selected_option < len(question["options"])):
            raise ValidationError(
                internal_detail=f"option out of range for question {item.question_id}"
            )
        answered[item.question_id] = item.selected_option

    if len(answered) != len(questions_by_id):
        raise ValidationError(internal_detail="all questions must be answered")

    return answered


def _score(assessment: Assessment, answered: dict[int, int]) -> int:
    """Calcula el puntaje en escala 0–100 (Req 7.2).

    El puntaje es la proporción de respuestas correctas redondeada a entero. Por
    construcción queda en [0, 100] (Property 23).
    """
    total = len(assessment.questions)
    if total == 0:
        return MIN_SCORE
    correct = sum(
        1 for q in assessment.questions if answered.get(q["id"]) == q["correct"]
    )
    score = round(correct * MAX_SCORE / total)
    return max(MIN_SCORE, min(MAX_SCORE, score))


async def _attempts_in_cycle(
    db: AsyncSession, current_user_id: uuid.UUID, path_id: uuid.UUID
) -> list[AssessmentAttempt]:
    """Devuelve los intentos del Usuario para la ruta, del más reciente al más antiguo.

    La consulta se ancla al `current_user_id` autenticado (anti-BOLA, Req 9.6).
    """
    stmt = (
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.profile_id == current_user_id,
            AssessmentAttempt.path_id == path_id,
        )
        .order_by(AssessmentAttempt.created_at.desc())
    )
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def submit_assessment(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    path_id: uuid.UUID,
    submission: AnswerSubmission,
    now: datetime | None = None,
) -> AttemptResult:
    """Valida, califica y registra un intento de evaluación.

    Flujo (Req 7.1–7.7):
    1. Recupera la evaluación (404 si no existe).
    2. Exige la ruta completada por el Usuario (409, Req 7.1) y que no haya
       aprobado ya la evaluación (409, Req 7.3): una evaluación aprobada no se
       vuelve a calificar.
    3. Rechaza si el Usuario está en enfriamiento vigente (429, Req 7.5).
    4. Valida las respuestas en servidor; inválidas → 422 sin puntaje (Req 7.6, 7.7).
    5. Calcula el puntaje 0–100 y marca aprobado si ≥ umbral (Req 7.2, 7.3).
    6. Controla el número de intento; al 3.º no aprobado activa enfriamiento 24 h
       y, pasado este, el contador se reinicia (Req 7.4, 7.5).
    """
    now = now or datetime.now(timezone.utc)
    assessment = await _get_assessment(db, path_id)
    await _require_path_completed(db, current_user_id, path_id)
    previous = await _attempts_in_cycle(db, current_user_id, path_id)

    # Una evaluación aprobada no se vuelve a calificar (Req 7.3).
    if any(attempt.passed for attempt in previous):
        log_event(logger, "assessment_already_passed")
        raise EvaluacionYaAprobadaError(internal_detail="assessment already passed")

    # Enfriamiento vigente: el último intento dejó una ventana aún no expirada.
    if previous and previous[0].cooldown_until is not None:
        if previous[0].cooldown_until > now:
            log_event(logger, "assessment_in_cooldown")
            raise RateLimitedError(internal_detail="assessment cooldown active")

    # Si el ciclo anterior terminó en enfriamiento ya expirado, se reinicia el
    # contador de intentos (Req 7.5): solo cuentan los intentos del ciclo vigente.
    cycle_attempts = _attempts_since_last_cooldown(previous)

    # Validación en servidor antes de calcular (Property 25).
    answered = _validate_answers(assessment, submission)
    score = _score(assessment, answered)
    passed = score >= assessment.pass_threshold

    attempt_number = cycle_attempts + 1
    cooldown_until: datetime | None = None
    if not passed and attempt_number >= MAX_ATTEMPTS:
        cooldown_until = now + timedelta(hours=COOLDOWN_HOURS)

    attempt = AssessmentAttempt(
        profile_id=current_user_id,
        path_id=path_id,
        score=score,
        passed=passed,
        attempt_number=attempt_number,
        cooldown_until=cooldown_until,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    attempts_remaining = 0 if passed else max(0, MAX_ATTEMPTS - attempt_number)
    log_event(
        logger,
        "assessment_attempt_recorded",
        score=score,
        passed=passed,
        attempt_number=attempt_number,
    )
    return AttemptResult(
        path_id=path_id,
        score=score,
        passed=passed,
        attempt_number=attempt_number,
        attempts_remaining=attempts_remaining,
        cooldown_until=cooldown_until.isoformat() if cooldown_until else None,
    )


def _attempts_since_last_cooldown(previous: list[AssessmentAttempt]) -> int:
    """Cuenta los intentos del ciclo vigente (posteriores al último enfriamiento).

    Los intentos están ordenados del más reciente al más antiguo. Un intento con
    `cooldown_until` marca el cierre de un ciclo; los intentos anteriores a él no
    cuentan para el ciclo actual (Req 7.5).
    """
    count = 0
    for attempt in previous:
        if attempt.cooldown_until is not None:
            # Este intento cerró un ciclo con enfriamiento (ya expirado si se
            # llegó hasta aquí): el contador se reinicia a partir de él.
            break
        count += 1
    return count
