"""Pruebas del enganche Learning → Gamification (Req 19.1, 19.2, 19.5, 19.6).

Al finalizar una microcápsula se otorga la insignia de cápsula; al completar la ruta,
también la de ruta. El otorgamiento es idempotente y un fallo pendiente de
Gamification no rompe la finalización: el progreso ya está guardado.
"""
from __future__ import annotations

import uuid

import pytest

from app.gamification.constants import (
    TRIGGER_MICROCAPSULA_COMPLETADA,
    TRIGGER_RUTA_COMPLETADA,
)
from app.gamification.errors import ReconocimientoPendienteError
from tests.learning.conftest import GrantCall
from tests.learning.test_completion import _finalize, _path, _progress, _Session


def _triggers(calls: list[GrantCall]) -> list[str]:
    return [call.trigger for call in calls]


@pytest.mark.asyncio
async def test_primera_capsula_otorga_solo_el_reconocimiento_de_capsula(
    grants: list[GrantCall],
) -> None:
    """Finalizar una cápsula de una ruta incompleta no otorga la insignia de ruta."""
    # Given una ruta de 2 cápsulas sin progreso
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    request_id = uuid.uuid4()

    # When se finaliza la primera
    await _finalize(_Session(path), user, c1, path, client_event_id=request_id)

    # Then solo se otorga el reconocimiento de cápsula, anclado al titular de la sesión
    assert _triggers(grants) == [TRIGGER_MICROCAPSULA_COMPLETADA]
    assert grants[0].profile_id == user
    assert grants[0].client_event_id == uuid.uuid5(request_id, TRIGGER_MICROCAPSULA_COMPLETADA)


@pytest.mark.asyncio
async def test_ultima_capsula_otorga_capsula_y_ruta_con_claves_distintas(
    grants: list[GrantCall],
) -> None:
    """Completar la ruta otorga ambos reconocimientos con claves derivadas distintas."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    request_id = uuid.uuid4()

    await _finalize(
        _Session(path, _progress(user, path, [c1])), user, c2, path, client_event_id=request_id
    )

    assert _triggers(grants) == [TRIGGER_MICROCAPSULA_COMPLETADA, TRIGGER_RUTA_COMPLETADA]
    assert grants[1].client_event_id == uuid.uuid5(request_id, TRIGGER_RUTA_COMPLETADA)
    assert grants[0].client_event_id != grants[1].client_event_id


@pytest.mark.asyncio
async def test_reintento_con_ruta_ya_completa_vuelve_a_intentar_la_insignia_de_ruta(
    grants: list[GrantCall],
) -> None:
    """Si el otorgamiento falló antes, el reintento lo recupera aunque ya no haya transición."""
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1, c2], completed=True))

    await _finalize(session, user, c2, path)

    # Gamification es idempotente (Req 19.5): intentarlo de nuevo es seguro.
    assert TRIGGER_RUTA_COMPLETADA in _triggers(grants)


@pytest.mark.asyncio
async def test_reconocimiento_pendiente_no_hace_fallar_la_finalizacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ReconocimientoPendienteError` se absorbe: la finalización responde con éxito (Req 19.6)."""
    attempted: list[str] = []

    async def _always_pending(db, profile_id, trigger, client_event_id):  # noqa: ANN001, ANN202
        attempted.append(trigger)
        raise ReconocimientoPendienteError(internal_detail="grant conflict")

    monkeypatch.setattr("app.gamification.service.grant_recognition", _always_pending)
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    path, user = _path(c1, c2), uuid.uuid4()
    session = _Session(path, _progress(user, path, [c1]))

    resp = await _finalize(session, user, c2, path)

    # La respuesta es correcta, el progreso quedó guardado y se intentaron ambos logros.
    assert resp.path_completed is True
    assert resp.completed_count == 2
    assert attempted == [TRIGGER_MICROCAPSULA_COMPLETADA, TRIGGER_RUTA_COMPLETADA]
    assert len(session.events_of("ruta_completada")) == 1


@pytest.mark.asyncio
async def test_otros_errores_de_gamification_no_se_ocultan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solo se absorbe el error de pendiente; cualquier otro error se propaga."""

    async def _broken(db, profile_id, trigger, client_event_id):  # noqa: ANN001, ANN202
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr("app.gamification.service.grant_recognition", _broken)
    c1 = uuid.uuid4()
    path, user = _path(c1), uuid.uuid4()

    with pytest.raises(RuntimeError):
        await _finalize(_Session(path), user, c1, path)
