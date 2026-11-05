"""Pruebas del Tablero de Impacto ODS (Tarea 18.3, Req 15).

Cubren: el vínculo métrica→ODS (Req 15.2), la supresión por k-anonimato de
zonas con < 5 Usuarios (Req 15.4), la exclusión de eventos sin zona, la ausencia
de PII en la salida (Req 15.3) y la autorización por rol administrativo en el
backend (`require_admin`, Req 15.5, 15.6).

No usan BD real: un stub de sesión en memoria agrega los eventos replicando el
filtro de k-anonimato y la exclusión de "sin_zona" que hace la consulta ORM.
Identificadores ficticios.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

import pytest

from app.common.errors import ForbiddenError
from app.common.security import require_admin
from app.impact import service
from app.impact.constants import ODS_8, ODS_10, ODS_13
from app.metrics.constants import K_ANONYMITY_THRESHOLD, UNCLASSIFIED_ZONE
from app.profile.models import ROLE_ADMIN, ROLE_USUARIO, Profile


class _Row:
    """Fila agregada equivalente a la que devuelve la consulta del servicio."""

    def __init__(self, geo_zone: str, event_type: str, total: int, distinct_users: int):
        self.geo_zone = geo_zone
        self.event_type = event_type
        self.total = total
        self.distinct_users = distinct_users


class _AggSession:
    """Sesión async cuyo `execute` agrega eventos en memoria como lo haría la BD.

    Recibe una lista de tuplas (geo_zone, event_type, profile_id) y reproduce la
    semántica del servicio: excluye "sin_zona", agrupa por (zona, tipo), cuenta
    eventos y Usuarios distintos, y suprime los grupos con menos de
    `K_ANONYMITY_THRESHOLD` Usuarios distintos (Req 15.4).
    """

    def __init__(self, eventos: list[tuple[str, str, uuid.UUID]]) -> None:
        self._eventos = eventos

    async def execute(self, _stmt):  # noqa: ANN001 - el stub ignora la query real
        grupos: dict[tuple[str, str], list[uuid.UUID]] = defaultdict(list)
        for zona, tipo, pid in self._eventos:
            if zona == UNCLASSIFIED_ZONE:
                continue
            grupos[(zona, tipo)].append(pid)

        filas = []
        for (zona, tipo), pids in sorted(grupos.items()):
            distintos = len(set(pids))
            if distintos >= K_ANONYMITY_THRESHOLD:
                filas.append(_Row(zona, tipo, total=len(pids), distinct_users=distintos))
        return iter(filas)


def _usuarios(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


# --- Servicio: agregación, ODS y k-anonimato --------------------------------


@pytest.mark.asyncio
async def test_vincula_cada_metrica_a_su_ods() -> None:
    """Cada tipo de evento del tablero se vincula a su ODS (Req 15.2)."""
    # 5 Usuarios distintos por tipo (supera el k-anonimato) en la misma zona.
    eventos: list[tuple[str, str, uuid.UUID]] = []
    for tipo in ("microcapsula_completada", "ruta_completada", "conversion_microseguro"):
        for pid in _usuarios(K_ANONYMITY_THRESHOLD):
            eventos.append(("zona-1", tipo, pid))

    db = _AggSession(eventos)
    tablero = await service.build_dashboard(db)

    ods_por_tipo = {m.event_type: m.ods for m in tablero.metrics}
    assert ods_por_tipo["microcapsula_completada"] == ODS_8
    assert ods_por_tipo["ruta_completada"] == ODS_10
    assert ods_por_tipo["conversion_microseguro"] == ODS_13


@pytest.mark.asyncio
async def test_suprime_zonas_bajo_el_umbral_de_k_anonimato() -> None:
    """Una zona con menos de 5 Usuarios distintos se suprime del tablero (Req 15.4)."""
    # Zona A con 5 Usuarios (pasa); zona B con 4 (se suprime).
    eventos = [("zona-A", "ruta_completada", pid) for pid in _usuarios(K_ANONYMITY_THRESHOLD)]
    eventos += [("zona-B", "ruta_completada", pid) for pid in _usuarios(K_ANONYMITY_THRESHOLD - 1)]

    db = _AggSession(eventos)
    tablero = await service.build_dashboard(db)

    zonas = {m.geo_zone for m in tablero.metrics}
    assert "zona-A" in zonas
    assert "zona-B" not in zonas


@pytest.mark.asyncio
async def test_excluye_eventos_sin_zona() -> None:
    """Los eventos sin zona clasificada no aparecen en el tablero (Req 15.3)."""
    eventos = [(UNCLASSIFIED_ZONE, "ruta_completada", pid) for pid in _usuarios(10)]
    db = _AggSession(eventos)
    tablero = await service.build_dashboard(db)
    assert tablero.metrics == []


@pytest.mark.asyncio
async def test_salida_no_contiene_pii() -> None:
    """La salida solo trae agregados: zona, tipo, ODS y conteos; sin ids de Usuario."""
    eventos = [("zona-1", "ruta_completada", pid) for pid in _usuarios(K_ANONYMITY_THRESHOLD)]
    db = _AggSession(eventos)
    tablero = await service.build_dashboard(db)
    assert len(tablero.metrics) == 1
    campos = set(tablero.metrics[0].model_dump().keys())
    assert campos == {"event_type", "label", "ods", "geo_zone", "total", "distinct_users"}


# --- Autorización por rol administrativo (require_admin) ---------------------


class _ProfileSession:
    """Sesión mínima cuyo `get` devuelve el Perfil precargado por id."""

    def __init__(self, profile: Profile | None) -> None:
        self._profile = profile

    async def get(self, _model, pk):  # noqa: ANN001
        if self._profile is not None and pk == self._profile.id:
            return self._profile
        return None


def _profile(role: str) -> Profile:
    return Profile(
        id=uuid.uuid4(),
        phone_e164="3001234567",
        clave_hash="hash",
        activity_type="cafe",
        geo_zone="zona-1",
        role=role,
    )


@pytest.mark.asyncio
async def test_require_admin_permite_rol_admin() -> None:
    """Un Usuario con rol admin pasa la verificación (Req 15.5)."""
    admin = _profile(ROLE_ADMIN)
    db = _ProfileSession(admin)
    resuelto = await require_admin(current_user_id=admin.id, db=db)
    assert resuelto == admin.id


@pytest.mark.asyncio
async def test_require_admin_rechaza_rol_usuario() -> None:
    """Un Usuario sin rol admin recibe error de autorización (Req 15.6)."""
    usuario = _profile(ROLE_USUARIO)
    db = _ProfileSession(usuario)
    with pytest.raises(ForbiddenError):
        await require_admin(current_user_id=usuario.id, db=db)


@pytest.mark.asyncio
async def test_require_admin_rechaza_perfil_inexistente() -> None:
    """Si el Perfil del token no existe, se rechaza (no se asume admin)."""
    db = _ProfileSession(profile=None)
    with pytest.raises(ForbiddenError):
        await require_admin(current_user_id=uuid.uuid4(), db=db)
