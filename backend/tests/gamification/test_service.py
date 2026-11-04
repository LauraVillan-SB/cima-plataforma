"""Pruebas del Gamification Service (Tarea 17.1).

Cubren el otorgamiento de Insignias y puntos (Req 19.1, 19.2), las reglas solo
en backend (Req 19.3), la idempotencia (Req 19.5) y los reintentos ante
conflictos de concurrencia con error específico si persisten (Req 19.6).

No usan BD real: una sesión en memoria simula `get`, `add`, `commit` y
`rollback`, y las consultas del servicio (`_find_by_event`, `_find_by_badge`,
`_get_points`) se sustituyen por versiones en memoria. Todos los identificadores
son ficticios.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.common.errors import NotFoundError, ValidationError
from app.gamification import service
from app.gamification.constants import (
    MAX_GRANT_ATTEMPTS,
    RECOGNITION_RULES,
    TRIGGER_MICROCAPSULA_COMPLETADA,
    TRIGGER_RUTA_COMPLETADA,
)
from app.gamification.dto import RecognitionGrantResult
from app.gamification.errors import ReconocimientoPendienteError
from app.gamification.models import UserBadge, UserPoints


class _FakeSession:
    """Sesión async mínima en memoria con transacciones y conflictos simulados.

    Lo agregado con `add` solo se persiste en `commit`; `rollback` lo descarta.
    `conflicts` indica cuántos `commit` consecutivos fallan con `IntegrityError`.
    """

    def __init__(self, profile_ids: list[uuid.UUID], conflicts: int = 0) -> None:
        self.profiles = set(profile_ids)
        self.badges: list[SimpleNamespace] = []
        self.points: dict[uuid.UUID, int] = {}
        self.conflicts_left = conflicts
        self.commits = 0
        self.rollbacks = 0
        self._pending_badges: list[UserBadge] = []
        self._new_points: list[UserPoints] = []
        self._locked_rows: list[SimpleNamespace] = []

    async def get(self, _model, pk):  # noqa: ANN001 - firma simplificada del stub
        return object() if pk in self.profiles else None

    def add(self, obj: object) -> None:
        if isinstance(obj, UserBadge):
            self._pending_badges.append(obj)
        elif isinstance(obj, UserPoints):
            self._new_points.append(obj)

    async def commit(self) -> None:
        if self.conflicts_left > 0:
            self.conflicts_left -= 1
            raise IntegrityError("conflicto simulado", {}, Exception("unique"))
        for badge in self._pending_badges:
            self.badges.append(
                SimpleNamespace(
                    profile_id=badge.profile_id,
                    badge_code=badge.badge_code,
                    client_event_id=badge.client_event_id,
                )
            )
        for fila in self._new_points:
            self.points[fila.profile_id] = fila.total_points
        for fila in self._locked_rows:
            self.points[fila.profile_id] = fila.total_points
        self.commits += 1
        self._discard_pending()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._discard_pending()

    def _discard_pending(self) -> None:
        self._pending_badges = []
        self._new_points = []
        self._locked_rows = []


async def _find_by_event(db: _FakeSession, client_event_id: uuid.UUID):
    return next((b for b in db.badges if b.client_event_id == client_event_id), None)


async def _find_by_badge(db: _FakeSession, profile_id: uuid.UUID, badge_code: str):
    return next(
        (b for b in db.badges if b.profile_id == profile_id and b.badge_code == badge_code),
        None,
    )


async def _get_points(db: _FakeSession, profile_id: uuid.UUID, lock: bool = False):
    total = db.points.get(profile_id)
    if total is None:
        return None
    fila = SimpleNamespace(profile_id=profile_id, total_points=total)
    if lock:
        db._locked_rows.append(fila)
    return fila


def _con_consultas_en_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sustituye las consultas del servicio por versiones en memoria."""
    monkeypatch.setattr(service, "_find_by_event", _find_by_event)
    monkeypatch.setattr(service, "_find_by_badge", _find_by_badge)
    monkeypatch.setattr(service, "_get_points", _get_points)


# --- Otorgamiento (Req 19.1, 19.2) -----------------------------------------


@pytest.mark.asyncio
async def test_otorga_insignia_y_puntos_por_microcapsula(monkeypatch: pytest.MonkeyPatch) -> None:
    """Completar una microcápsula otorga su Insignia y sus puntos (Req 19.1)."""
    # Given un Perfil existente
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil])
    regla = RECOGNITION_RULES[TRIGGER_MICROCAPSULA_COMPLETADA]
    # When se otorga el reconocimiento de la microcápsula
    resultado = await service.grant_recognition(
        db, perfil, TRIGGER_MICROCAPSULA_COMPLETADA, uuid.uuid4()
    )
    # Then queda registrada la Insignia y el total refleja sus puntos
    assert resultado.newly_awarded is True
    assert resultado.badge_code == regla.code
    assert resultado.total_points == regla.points
    assert len(db.badges) == 1 and db.points[perfil] == regla.points


@pytest.mark.asyncio
async def test_otorga_insignia_y_puntos_por_ruta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Completar una ruta otorga su Insignia y sus puntos (Req 19.1)."""
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil])
    regla = RECOGNITION_RULES[TRIGGER_RUTA_COMPLETADA]
    resultado = await service.grant_recognition(
        db, perfil, TRIGGER_RUTA_COMPLETADA, uuid.uuid4()
    )
    assert resultado.badge_code == regla.code
    assert resultado.total_points == regla.points


@pytest.mark.asyncio
async def test_suma_puntos_de_insignias_distintas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos logros distintos suman los puntos de ambas Insignias (Req 19.2)."""
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil])
    await service.grant_recognition(db, perfil, TRIGGER_MICROCAPSULA_COMPLETADA, uuid.uuid4())
    resultado = await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, uuid.uuid4())
    esperado = sum(regla.points for regla in RECOGNITION_RULES.values())
    assert resultado.total_points == esperado
    assert len(db.badges) == 2


# --- Idempotencia (Req 19.5) ------------------------------------------------


@pytest.mark.asyncio
async def test_reintento_con_el_mismo_evento_no_duplica(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repetir el mismo client_event_id devuelve lo existente sin duplicar."""
    # Given un otorgamiento ya hecho
    _con_consultas_en_memoria(monkeypatch)
    perfil, evento = uuid.uuid4(), uuid.uuid4()
    db = _FakeSession([perfil])
    primero = await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, evento)
    # When se reintenta con el mismo evento
    segundo = await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, evento)
    # Then no hay duplicado y los puntos no se vuelven a sumar
    assert segundo.newly_awarded is False
    assert segundo.total_points == primero.total_points
    assert len(db.badges) == 1


@pytest.mark.asyncio
async def test_misma_insignia_con_eventos_distintos_no_duplica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una secuencia de otorgamientos de la misma Insignia deja un solo registro."""
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil])
    regla = RECOGNITION_RULES[TRIGGER_MICROCAPSULA_COMPLETADA]
    for _ in range(5):
        resultado = await service.grant_recognition(
            db, perfil, TRIGGER_MICROCAPSULA_COMPLETADA, uuid.uuid4()
        )
    assert len(db.badges) == 1
    assert resultado.total_points == regla.points
    assert db.points[perfil] == regla.points


@pytest.mark.asyncio
async def test_rechaza_reusar_evento_en_otra_insignia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un client_event_id ya usado no puede otorgar otra Insignia."""
    _con_consultas_en_memoria(monkeypatch)
    perfil, evento = uuid.uuid4(), uuid.uuid4()
    db = _FakeSession([perfil])
    await service.grant_recognition(db, perfil, TRIGGER_MICROCAPSULA_COMPLETADA, evento)
    with pytest.raises(ValidationError):
        await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, evento)
    assert len(db.badges) == 1


@pytest.mark.asyncio
async def test_rechaza_reusar_evento_de_otro_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un client_event_id de otro Perfil no otorga nada ni revela datos ajenos."""
    _con_consultas_en_memoria(monkeypatch)
    perfil_a, perfil_b, evento = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    db = _FakeSession([perfil_a, perfil_b])
    await service.grant_recognition(db, perfil_a, TRIGGER_RUTA_COMPLETADA, evento)
    with pytest.raises(ValidationError):
        await service.grant_recognition(db, perfil_b, TRIGGER_RUTA_COMPLETADA, evento)
    assert perfil_b not in db.points
    assert all(b.profile_id == perfil_a for b in db.badges)


# --- Validación (Req 19.3) --------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("trigger", ["", "admin", "ruta_completada ", "RUTA_COMPLETADA", "x" * 200])
async def test_rechaza_logro_fuera_del_catalogo(
    trigger: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Solo se otorgan logros del catálogo del backend; lo demás se rechaza."""
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil])
    with pytest.raises(ValidationError):
        await service.grant_recognition(db, perfil, trigger, uuid.uuid4())
    assert db.badges == [] and db.points == {}


@pytest.mark.asyncio
async def test_falla_si_no_existe_el_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    """No se otorga nada a un Perfil inexistente."""
    _con_consultas_en_memoria(monkeypatch)
    db = _FakeSession([])
    with pytest.raises(NotFoundError):
        await service.grant_recognition(
            db, uuid.uuid4(), TRIGGER_RUTA_COMPLETADA, uuid.uuid4()
        )
    assert db.badges == []


# --- Reintentos y conflictos (Req 19.6) -------------------------------------


@pytest.mark.asyncio
async def test_reintenta_ante_conflicto_y_otorga(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos conflictos seguidos se reintentan y el tercer intento otorga."""
    # Given dos conflictos de concurrencia antes de poder confirmar
    _con_consultas_en_memoria(monkeypatch)
    perfil = uuid.uuid4()
    db = _FakeSession([perfil], conflicts=2)
    # When se otorga el reconocimiento
    resultado = await service.grant_recognition(
        db, perfil, TRIGGER_RUTA_COMPLETADA, uuid.uuid4()
    )
    # Then se otorgó una sola vez tras reintentar
    assert resultado.newly_awarded is True
    assert db.rollbacks == 2 and len(db.badges) == 1


@pytest.mark.asyncio
async def test_error_especifico_tras_agotar_reintentos_y_luego_se_recupera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si persisten los conflictos, falla con error específico y el evento se conserva."""
    # Given conflictos en todos los intentos
    _con_consultas_en_memoria(monkeypatch)
    perfil, evento = uuid.uuid4(), uuid.uuid4()
    db = _FakeSession([perfil], conflicts=MAX_GRANT_ATTEMPTS)
    # When / Then falla con el error del dominio y no deja nada a medias
    with pytest.raises(ReconocimientoPendienteError):
        await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, evento)
    assert db.rollbacks == MAX_GRANT_ATTEMPTS
    assert db.badges == [] and db.points == {}
    # And al reintentar luego con el MISMO evento, se otorga sin duplicar
    resultado = await service.grant_recognition(db, perfil, TRIGGER_RUTA_COMPLETADA, evento)
    assert resultado.newly_awarded is True and len(db.badges) == 1


# --- Catálogo y resultado ---------------------------------------------------


def test_catalogo_de_reglas_es_valido() -> None:
    """Cada regla tiene puntos positivos y los códigos de Insignia no se repiten."""
    codigos = [regla.code for regla in RECOGNITION_RULES.values()]
    assert len(codigos) == len(set(codigos))
    assert all(regla.points > 0 for regla in RECOGNITION_RULES.values())


def test_resultado_expone_solo_campos_permitidos() -> None:
    """El DTO de resultado no incluye identificadores del Perfil ni PII."""
    campos = set(RecognitionGrantResult.__annotations__)
    assert campos == {"badge_code", "badge_name", "total_points", "newly_awarded"}
