"""Pruebas de la consulta de reconocimientos (Tarea 17.2).

Cubren que la consulta devuelve solo las Insignias y puntos del titular
autenticado (Req 19.7), que el acceso a reconocimientos de otro Perfil se
rechaza con error de autorización sin consultar la base de datos ni revelar si
ese Perfil existe, y que el intento se registra sin PII (Req 19.8).

No usan BD real: `_list_badges` y `_get_points` se sustituyen por versiones en
memoria. Todos los identificadores son ficticios.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.common.errors import ForbiddenError
from app.gamification import service
from app.gamification.constants import BADGE_NAMES, RECOGNITION_RULES
from app.gamification.dto import BadgeOut, RecognitionSummary


def _insignia(profile_id: uuid.UUID, badge_code: str) -> SimpleNamespace:
    """Crea una Insignia ficticia en memoria."""
    return SimpleNamespace(profile_id=profile_id, badge_code=badge_code)


def _con_datos(
    monkeypatch: pytest.MonkeyPatch,
    badges: list[SimpleNamespace],
    points: dict[uuid.UUID, int],
) -> dict[str, int]:
    """Sustituye las consultas por versiones en memoria y cuenta las llamadas.

    Devuelve un contador con las veces que se consultó cada tabla, para verificar
    que un acceso rechazado no llega a la base de datos.
    """
    llamadas = {"badges": 0, "points": 0}

    async def _list_badges(_db: object, profile_id: uuid.UUID):
        llamadas["badges"] += 1
        return [b for b in badges if b.profile_id == profile_id]

    async def _get_points(_db: object, profile_id: uuid.UUID, lock: bool = False):
        llamadas["points"] += 1
        total = points.get(profile_id)
        return None if total is None else SimpleNamespace(total_points=total)

    monkeypatch.setattr(service, "_list_badges", _list_badges)
    monkeypatch.setattr(service, "_get_points", _get_points)
    return llamadas


# --- Consulta del titular (Req 19.7) ----------------------------------------


@pytest.mark.asyncio
async def test_lista_insignias_y_puntos_del_titular(monkeypatch: pytest.MonkeyPatch) -> None:
    """La consulta devuelve las Insignias con su nombre y el total de puntos."""
    # Given un Perfil con las dos Insignias del catálogo
    titular = uuid.uuid4()
    reglas = list(RECOGNITION_RULES.values())
    _con_datos(
        monkeypatch,
        [_insignia(titular, regla.code) for regla in reglas],
        {titular: sum(regla.points for regla in reglas)},
    )
    # When consulta sus reconocimientos
    resumen = await service.get_recognitions(object(), titular)
    # Then ve sus Insignias con nombre legible y el total de puntos
    assert [b.badge_code for b in resumen.badges] == [regla.code for regla in reglas]
    assert [b.badge_name for b in resumen.badges] == [regla.name for regla in reglas]
    assert resumen.total_points == sum(regla.points for regla in reglas)


@pytest.mark.asyncio
async def test_devuelve_solo_lo_del_titular(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las Insignias y puntos de otros Perfiles nunca aparecen en la respuesta."""
    # Given dos Perfiles con reconocimientos distintos
    titular, otro = uuid.uuid4(), uuid.uuid4()
    _con_datos(
        monkeypatch,
        [_insignia(titular, "primer_paso"), _insignia(otro, "ruta_completada")],
        {titular: 10, otro: 50},
    )
    # When el titular consulta
    resumen = await service.get_recognitions(object(), titular)
    # Then solo ve lo suyo
    assert [b.badge_code for b in resumen.badges] == ["primer_paso"]
    assert resumen.total_points == 10


@pytest.mark.asyncio
async def test_sin_reconocimientos_devuelve_vacio_y_cero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un Perfil sin Insignias ni puntos recibe una lista vacía y 0 puntos."""
    _con_datos(monkeypatch, [], {})
    resumen = await service.get_recognitions(object(), uuid.uuid4())
    assert resumen.badges == [] and resumen.total_points == 0


@pytest.mark.asyncio
async def test_acepta_el_perfil_propio_como_parametro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pedir explícitamente el propio Perfil es válido."""
    titular = uuid.uuid4()
    _con_datos(monkeypatch, [_insignia(titular, "primer_paso")], {titular: 10})
    resumen = await service.get_recognitions(object(), titular, titular)
    assert resumen.total_points == 10


@pytest.mark.asyncio
async def test_insignia_fuera_del_catalogo_usa_el_codigo_como_nombre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una Insignia retirada del catálogo se lista con su código, sin fallar."""
    titular = uuid.uuid4()
    _con_datos(monkeypatch, [_insignia(titular, "insignia_retirada")], {titular: 5})
    resumen = await service.get_recognitions(object(), titular)
    assert resumen.badges[0].badge_name == "insignia_retirada"


# --- Acceso a reconocimientos ajenos (Req 19.8) -----------------------------


@pytest.mark.asyncio
async def test_rechaza_perfil_ajeno_sin_consultar_la_bd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pedir otro Perfil falla con error de autorización antes de tocar la BD."""
    # Given un Usuario que pide los reconocimientos de otro Perfil
    atacante, victima = uuid.uuid4(), uuid.uuid4()
    llamadas = _con_datos(
        monkeypatch, [_insignia(victima, "ruta_completada")], {victima: 50}
    )
    # When / Then se rechaza y no se consultó ninguna tabla
    with pytest.raises(ForbiddenError):
        await service.get_recognitions(object(), atacante, victima)
    assert llamadas == {"badges": 0, "points": 0}


@pytest.mark.asyncio
async def test_rechazo_igual_exista_o_no_el_perfil_ajeno(monkeypatch: pytest.MonkeyPatch) -> None:
    """La respuesta de rechazo no revela si el Perfil solicitado existe."""
    atacante, existente, inexistente = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    _con_datos(monkeypatch, [_insignia(existente, "primer_paso")], {existente: 10})
    errores = []
    for objetivo in (existente, inexistente):
        with pytest.raises(ForbiddenError) as error:
            await service.get_recognitions(object(), atacante, objetivo)
        errores.append(error.value)
    assert errores[0].public_message == errores[1].public_message
    assert errores[0].internal_detail == errores[1].internal_detail


@pytest.mark.asyncio
async def test_registra_el_intento_ajeno_sin_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """El intento se registra solo con identificadores internos, sin datos del Perfil."""
    # Given un registro de eventos capturado
    atacante, victima = uuid.uuid4(), uuid.uuid4()
    _con_datos(monkeypatch, [_insignia(victima, "ruta_completada")], {victima: 50})
    eventos: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        service, "log_event", lambda _logger, mensaje, **ctx: eventos.append((mensaje, ctx))
    )
    # When se intenta ver los reconocimientos ajenos
    with pytest.raises(ForbiddenError):
        await service.get_recognitions(object(), atacante, victima)
    # Then se registró un único evento que solo contiene los dos identificadores
    assert eventos == [
        (
            "gamification_bola_attempt_blocked",
            {"actor_id": str(atacante), "target_id": str(victima)},
        )
    ]


# --- Catálogo y DTOs --------------------------------------------------------


def test_nombres_de_insignia_cubren_el_catalogo() -> None:
    """Toda Insignia del catálogo tiene nombre legible."""
    assert set(BADGE_NAMES) == {regla.code for regla in RECOGNITION_RULES.values()}


def test_dtos_de_consulta_exponen_solo_campos_permitidos() -> None:
    """Las respuestas no incluyen el identificador del Perfil ni PII."""
    assert set(BadgeOut.__annotations__) == {"badge_code", "badge_name"}
    assert set(RecognitionSummary.__annotations__) == {"badges", "total_points"}
