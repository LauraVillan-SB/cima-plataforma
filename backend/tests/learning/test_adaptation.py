"""Pruebas de la adaptación del aprendizaje y del contador de solicitudes de actividad.

Feature: cima-plataforma.
- Req 17.1: repetir una cápsula, exceder el tiempo esperado o fallar la comprobación
  de comprensión simplifica y baja el ritmo de la microcápsula siguiente.
- Req 17.2/17.5: sin señales la ruta es la estándar; no se pide nada al Usuario.
- Req 4.7: el reintento de red de la misma petición no cuenta como repetición.
- Req 4.8/4.9: el agente pide la actividad hasta 3 veces; después, tema general.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.learning import service
from app.learning.constants import (
    EXPECTED_TIME_FACTOR,
    FALLBACK_TOPIC,
    MAX_ELAPSED_SEC,
    PACE_SLOW,
    PACE_STANDARD,
)
from app.learning.dto import FinalizeRequest
from app.learning.models import Microcapsule
from tests.learning.test_completion import _path, _progress, _Session

_DURATION = 200


def _capsule(capsule_id: uuid.UUID) -> Microcapsule:
    return Microcapsule(
        id=capsule_id,
        topic=FALLBACK_TOPIC,
        activity_tags=["cafe"],
        duration_sec=_DURATION,
        relevance=1,
        difficulty=0,
    )


async def _finalize(session, user, capsule, path, event_id=None, elapsed=None):  # noqa: ANN001, ANN201
    request = FinalizeRequest(
        client_event_id=event_id or uuid.uuid4(), path_id=path.id, elapsed_seconds=elapsed
    )
    return await service.finalize_microcapsule(session, user, capsule, request)


# --------------------------------------------------------------------------- #
# Req 17.1 — Señales de repetición y de tiempo
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_primera_finalizacion_normal_mantiene_la_ruta_estandar() -> None:
    """Sin señales (primera vez, sin exceso de tiempo) la ruta es la estándar (Req 17.5)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, capsules={c1: _capsule(c1)})

    await _finalize(session, user, c1, path, elapsed=_DURATION)
    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is False
    assert status.adapted is False
    assert status.pace == PACE_STANDARD


@pytest.mark.asyncio
async def test_repetir_una_capsula_simplifica_y_baja_el_ritmo() -> None:
    """Repetir una cápsula ya finalizada (otro `client_event_id`) es una señal (Req 17.1)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)

    await _finalize(session, user, c1, path)
    await _finalize(session, user, c1, path)
    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is True
    assert status.adapted is True
    assert status.pace == PACE_SLOW
    assert status.next_microcapsule_id == c2


@pytest.mark.asyncio
async def test_reintento_de_red_no_cuenta_como_repeticion() -> None:
    """La misma petición reenviada (mismo `client_event_id`) no es una señal (Req 4.7)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path)
    event_id = uuid.uuid4()

    await _finalize(session, user, c1, path, event_id=event_id)
    await _finalize(session, user, c1, path, event_id=event_id)
    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is False
    assert session._progress.repeat_count == 0


@pytest.mark.asyncio
async def test_exceder_el_tiempo_esperado_simplifica() -> None:
    """Tardar más de `EXPECTED_TIME_FACTOR` veces la duración es una señal (Req 17.1)."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, capsules={c1: _capsule(c1)})

    await _finalize(session, user, c1, path, elapsed=_DURATION * EXPECTED_TIME_FACTOR + 1)
    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is True
    assert status.pace == PACE_SLOW
    assert session._progress.slow_count == 1


@pytest.mark.asyncio
async def test_tiempo_justo_en_el_limite_no_es_exceso() -> None:
    """Exactamente el tiempo esperado por el factor no excede (el límite es estricto)."""
    c1 = uuid.uuid4()
    path, user = _path(c1), uuid.uuid4()
    session = _Session(path, capsules={c1: _capsule(c1)})

    await _finalize(session, user, c1, path, elapsed=_DURATION * EXPECTED_TIME_FACTOR)

    assert session._progress.slow_count == 0
    assert session._progress.needs_simplification is False


@pytest.mark.asyncio
async def test_sin_tiempo_reportado_no_hay_senal_de_tiempo() -> None:
    """Si el cliente no reporta tiempo, el tiempo no genera señal (Req 17.2)."""
    c1 = uuid.uuid4()
    path, user = _path(c1), uuid.uuid4()
    session = _Session(path)

    await _finalize(session, user, c1, path, elapsed=None)

    assert session._progress.slow_count == 0


@pytest.mark.asyncio
async def test_una_finalizacion_normal_posterior_vuelve_al_ritmo_estandar() -> None:
    """Tras simplificar, completar la siguiente sin problemas restablece el ritmo."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]), capsules={c2: _capsule(c2)})
    session._progress.needs_simplification = True

    await _finalize(session, user, c2, path, elapsed=_DURATION)
    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is False
    assert status.pace == PACE_STANDARD


# --------------------------------------------------------------------------- #
# Req 17.1 — Comprobación de comprensión (evaluación)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fallar_la_evaluacion_simplifica() -> None:
    """Intentos de evaluación sin aprobar son una señal de falla de comprensión."""
    c1 = uuid.uuid4()
    path, user = _path(c1), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1], completed=True), attempts=[False, False])

    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is True
    assert status.pace == PACE_SLOW


@pytest.mark.asyncio
async def test_evaluacion_aprobada_deja_de_ser_senal() -> None:
    """Si el Usuario ya aprobó, los intentos fallidos previos dejan de contar."""
    c1 = uuid.uuid4()
    path, user = _path(c1), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1], completed=True), attempts=[False, True])

    status = await service.get_path_status(session, user, path.id)

    assert status.simplify is False


# --------------------------------------------------------------------------- #
# Req 4.8 / 4.9 — Contador de solicitudes de actividad
# --------------------------------------------------------------------------- #
class _PromptSession:
    """Sesión mínima para `select_for_user`: perfil sin actividad y contador simulado."""

    def __init__(self, counts: list[int | None]) -> None:
        self._counts = list(counts)
        self.commits = 0

    async def get(self, _model, _pk):  # noqa: ANN001, ANN201
        class _Profile:
            activity_type = None

        return _Profile()

    async def scalar(self, _stmt):  # noqa: ANN001, ANN201
        return self._counts.pop(0)

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, _stmt):  # noqa: ANN001, ANN201
        from tests.learning.test_selection import _capsule as general_capsule
        from tests.learning.test_selection import _ScalarsResult

        return _ScalarsResult([general_capsule(topic=FALLBACK_TOPIC, tags=["general"])])


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2, 3])
async def test_las_primeras_tres_solicitudes_piden_la_actividad(count: int) -> None:
    """Mientras el contador acepta la solicitud, el agente debe pedir la actividad (Req 4.8)."""
    session = _PromptSession([count])

    result = await service.select_for_user(session, uuid.uuid4())

    assert result.prompt_activity is True
    assert result.fallback is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_agotadas_las_tres_solicitudes_entrega_tema_general_sin_pedir() -> None:
    """Con el contador agotado deja de pedir y entrega el tema general (Req 4.9)."""
    session = _PromptSession([None])

    result = await service.select_for_user(session, uuid.uuid4())

    assert result.prompt_activity is False
    assert result.fallback is True
    assert result.notice is None
    assert result.items
    assert all(item.topic == FALLBACK_TOPIC for item in result.items)


# --------------------------------------------------------------------------- #
# Validación del DTO de entrada
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("elapsed", [-1, MAX_ELAPSED_SEC + 1])
def test_tiempo_reportado_fuera_de_rango_se_rechaza(elapsed: int) -> None:
    """`elapsed_seconds` se valida en servidor: no negativo y con tope de 24 h."""
    with pytest.raises(PydanticValidationError):
        FinalizeRequest(client_event_id=uuid.uuid4(), path_id=uuid.uuid4(), elapsed_seconds=elapsed)


def test_tiempo_reportado_es_opcional_y_se_rechazan_claves_extra() -> None:
    """Sin `elapsed_seconds` el cuerpo es válido; una clave inesperada se rechaza."""
    ok = FinalizeRequest(client_event_id=uuid.uuid4(), path_id=uuid.uuid4())
    assert ok.elapsed_seconds is None

    with pytest.raises(PydanticValidationError):
        FinalizeRequest(
            client_event_id=uuid.uuid4(), path_id=uuid.uuid4(), rol="admin"  # type: ignore[call-arg]
        )
