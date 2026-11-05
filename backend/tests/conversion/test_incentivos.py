"""Pruebas de la entrega de incentivos del Conversion Service (Tarea 16.1).

Feature: cima-plataforma, Property 16: Invariante de estado de entrega de incentivo.
Validates: Requirements 5.1, 5.2, 5.3.

No usan BD real: un stub de sesión en memoria resuelve el progreso de ruta
(`PathProgress`) y el incentivo (`Incentive`) por sus filtros, y simula
`add/commit/refresh`. El canal de entrega se inyecta para forzar éxito o fallo
de forma determinista, sin dependencias externas. Identificadores ficticios.
"""
from __future__ import annotations

import uuid

import pytest

from app.common.errors import ValidationError
from app.conversion import service
from app.conversion.constants import (
    INCENTIVE_STATUS_ENTREGADO,
    INCENTIVE_STATUS_PENDIENTE,
    MAX_INCENTIVE_DELIVERY_ATTEMPTS,
)
from app.conversion.dto import IncentiveDeliveryRequest
from app.conversion.models import Incentive
from app.learning.models import PathProgress

_PATH_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _progress(completed: bool, profile_id: uuid.UUID = _USER_ID) -> PathProgress:
    """Progreso de ruta ficticio con la marca de completitud indicada."""
    return PathProgress(
        id=uuid.uuid4(),
        profile_id=profile_id,
        path_id=_PATH_ID,
        completed_microcapsules=[],
        completed=completed,
        last_completed_step=0,
    )


def _request() -> IncentiveDeliveryRequest:
    return IncentiveDeliveryRequest(
        client_event_id=uuid.uuid4(), incentive_type="bono_formacion"
    )


class _FakeSession:
    """Sesión async que resuelve PathProgress e Incentive según el filtro.

    Entrega el progreso precargado y el incentivo precargado (o None). Simula
    `add/commit/refresh` asignando id al incentivo nuevo, como haría la BD.
    """

    def __init__(
        self, progress: PathProgress | None, incentive: Incentive | None = None
    ) -> None:
        self._progress = progress
        self._incentive = incentive
        self.added: list[object] = []
        self.commits = 0

    async def scalar(self, stmt):  # noqa: ANN001 - el stub inspecciona la entidad
        entity = stmt.column_descriptions[0]["entity"]
        if entity is PathProgress:
            return self._progress
        if entity is Incentive:
            return self._incentive
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, Incentive):
            self._incentive = obj

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: object) -> None:
        if isinstance(obj, Incentive) and obj.id is None:
            obj.id = uuid.uuid4()


async def _ok_channel(_i: Incentive) -> bool:
    return True


async def _fail_channel(_i: Incentive) -> bool:
    return False


# --- Camino feliz y verificación de completitud -----------------------------


@pytest.mark.asyncio
async def test_entrega_exitosa_marca_entregado() -> None:
    """Ruta completada + canal OK → incentivo entregado con confirmación (Req 5.1)."""
    db = _FakeSession(progress=_progress(completed=True))
    result = await service.entregar_incentivo(
        db, _PATH_ID, _USER_ID, _request(), delivery_channel=_ok_channel
    )
    assert result.delivered is True
    assert result.status == INCENTIVE_STATUS_ENTREGADO
    assert result.retry_count == 0
    assert result.exhausted is False


@pytest.mark.asyncio
async def test_ruta_no_completada_rechaza_sin_crear_incentivo() -> None:
    """Sin completitud de ruta, la entrega se rechaza (Req 5.1); no se crea incentivo."""
    db = _FakeSession(progress=_progress(completed=False))
    with pytest.raises(ValidationError):
        await service.entregar_incentivo(
            db, _PATH_ID, _USER_ID, _request(), delivery_channel=_ok_channel
        )
    assert not any(isinstance(o, Incentive) for o in db.added)


@pytest.mark.asyncio
async def test_sin_progreso_rechaza() -> None:
    """Sin registro de progreso para el Usuario, la entrega se rechaza (anti-BOLA)."""
    db = _FakeSession(progress=None)
    with pytest.raises(ValidationError):
        await service.entregar_incentivo(
            db, _PATH_ID, _USER_ID, _request(), delivery_channel=_ok_channel
        )


# --- Fallos, reintentos y agotamiento (Property 16) -------------------------


@pytest.mark.asyncio
async def test_fallo_incrementa_retry_y_deja_pendiente() -> None:
    """Un fallo de entrega cuenta el intento y conserva el incentivo pendiente (Req 5.2)."""
    db = _FakeSession(progress=_progress(completed=True))
    result = await service.entregar_incentivo(
        db, _PATH_ID, _USER_ID, _request(), delivery_channel=_fail_channel
    )
    assert result.delivered is False
    assert result.status == INCENTIVE_STATUS_PENDIENTE
    assert result.retry_count == 1
    assert result.exhausted is False


# Feature: cima-plataforma, Property 16: Invariante de estado de entrega de incentivo.
# Validates: Requirements 5.1, 5.2, 5.3
@pytest.mark.asyncio
async def test_property_16_reintentos_acotados_y_pendiente_definitivo() -> None:
    """Tras 3 fallos, el incentivo queda pendiente definitivo; retry_count no excede 3.

    La completitud de la ruta se conserva en todo momento (el servicio nunca
    toca `path_progress.completed`). Invariante de la Property 16.
    """
    progress = _progress(completed=True)
    db = _FakeSession(progress=progress)
    req = _request()

    result = None
    # Se reinvoca la entrega como lo haría el worker de reintentos; el canal
    # siempre falla. Más invocaciones que el máximo para verificar el tope.
    for _ in range(MAX_INCENTIVE_DELIVERY_ATTEMPTS + 2):
        result = await service.entregar_incentivo(
            db, _PATH_ID, _USER_ID, req, delivery_channel=_fail_channel
        )

    assert result is not None
    assert result.delivered is False
    assert result.status == INCENTIVE_STATUS_PENDIENTE
    # retry_count nunca supera el máximo (3), aunque se reintente más veces.
    assert result.retry_count == MAX_INCENTIVE_DELIVERY_ATTEMPTS
    assert result.exhausted is True
    # La completitud de la ruta se conserva intacta (Req 5.2, 5.3).
    assert progress.completed is True


@pytest.mark.asyncio
async def test_idempotente_no_reentrega_si_ya_entregado() -> None:
    """Un incentivo ya entregado no se vuelve a entregar (idempotencia, Req 5.1)."""
    entregado = Incentive(
        id=uuid.uuid4(),
        profile_id=_USER_ID,
        path_id=_PATH_ID,
        incentive_type="bono_formacion",
        delivery_status=INCENTIVE_STATUS_ENTREGADO,
        retry_count=0,
    )
    db = _FakeSession(progress=_progress(completed=True), incentive=entregado)
    # Aunque el canal fallara, no debe intentarse de nuevo: ya está entregado.
    result = await service.entregar_incentivo(
        db, _PATH_ID, _USER_ID, _request(), delivery_channel=_fail_channel
    )
    assert result.delivered is True
    assert result.status == INCENTIVE_STATUS_ENTREGADO
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_recuperacion_tras_fallos_puede_entregar() -> None:
    """Un incentivo pendiente con reintentos < 3 puede entregarse si el canal se recupera."""
    pendiente = Incentive(
        id=uuid.uuid4(),
        profile_id=_USER_ID,
        path_id=_PATH_ID,
        incentive_type="bono_formacion",
        delivery_status=INCENTIVE_STATUS_PENDIENTE,
        retry_count=2,
    )
    db = _FakeSession(progress=_progress(completed=True), incentive=pendiente)
    result = await service.entregar_incentivo(
        db, _PATH_ID, _USER_ID, _request(), delivery_channel=_ok_channel
    )
    assert result.delivered is True
    assert result.status == INCENTIVE_STATUS_ENTREGADO
    # El contador no se incrementa en un intento exitoso.
    assert result.retry_count == 2
