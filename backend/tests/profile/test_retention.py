"""Pruebas de la retención/anonimización de datos sensibles del Perfil.

Feature: cima-plataforma, Property 29: Retención de datos sensibles a 90 días.

No usan BD real: un stub de sesión en memoria simula `scalars`/`commit`. El
reloj se controla con el parámetro `ahora` del servicio.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.common.config import get_settings
from app.profile import retention
from app.profile.models import Profile

_RETENCION_DIAS = get_settings().data_retention_days


class _FakeResult:
    """Resultado iterable que imita lo devuelto por `AsyncSession.scalars`."""

    def __init__(self, items: list[Profile]) -> None:
        self._items = items

    def __iter__(self):
        return iter(self._items)


class _FakeSession:
    """Sesión async que filtra los perfiles vencidos en memoria.

    Reproduce la condición del servicio: `created_at <= umbral` y teléfono no
    anonimizado aún. El umbral se recalcula con el mismo `ahora` de la prueba.
    """

    def __init__(self, perfiles: list[Profile], umbral: datetime) -> None:
        self._perfiles = perfiles
        self._umbral = umbral
        self.commits = 0

    async def scalars(self, _stmt) -> _FakeResult:
        vencidos = [
            p
            for p in self._perfiles
            if p.created_at <= self._umbral and p.phone_e164 != retention.ANON_PHONE
        ]
        return _FakeResult(vencidos)

    async def commit(self) -> None:
        self.commits += 1


def _perfil(created_at: datetime) -> Profile:
    return Profile(
        id=uuid.uuid4(),
        phone_e164="3001234567",
        clave_hash="hash-real",
        activity_type="cafe",
        geo_zone="zona-1",
        created_at=created_at,
    )


# Feature: cima-plataforma, Property 29: Retención de datos sensibles a 90 días.
# Validates: Requirements 8.8, 9.8
@settings(max_examples=100, deadline=None)
@given(dias=st.integers(min_value=0, max_value=400))
@pytest.mark.asyncio
async def test_property_29_anonimizacion_por_antiguedad(dias: int) -> None:
    """La PII se anonimiza si y solo si el Perfil tiene ≥ `data_retention_days`."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    perfil = _perfil(created_at=ahora - timedelta(days=dias))
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    sesion = _FakeSession([perfil], umbral)

    await retention.anonimizar_perfiles_vencidos(sesion, ahora=ahora)

    if dias >= _RETENCION_DIAS:
        # PII ya no recuperable
        assert perfil.phone_e164 == retention.ANON_PHONE
        assert perfil.clave_hash == retention.ANON_CLAVE_HASH
    else:
        # Dentro de la ventana de retención: la PII se conserva intacta
        assert perfil.phone_e164 == "3001234567"
        assert perfil.clave_hash == "hash-real"


@pytest.mark.asyncio
async def test_retencion_es_idempotente() -> None:
    """Ejecutar la retención dos veces no re-procesa perfiles ya anonimizados."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    perfil = _perfil(created_at=ahora - timedelta(days=200))
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    sesion = _FakeSession([perfil], umbral)

    primera = await retention.anonimizar_perfiles_vencidos(sesion, ahora=ahora)
    segunda = await retention.anonimizar_perfiles_vencidos(sesion, ahora=ahora)

    assert primera == 1
    assert segunda == 0  # ya anonimizado, no se vuelve a contar


@pytest.mark.asyncio
async def test_retencion_devuelve_conteo_de_anonimizados() -> None:
    """El servicio devuelve cuántos perfiles anonimizó en la ejecución."""
    ahora = datetime(2026, 6, 1, tzinfo=timezone.utc)
    umbral = ahora - timedelta(days=_RETENCION_DIAS)
    vencidos = [_perfil(created_at=ahora - timedelta(days=120)) for _ in range(3)]
    vigente = _perfil(created_at=ahora - timedelta(days=10))
    sesion = _FakeSession(vencidos + [vigente], umbral)

    anonimizados = await retention.anonimizar_perfiles_vencidos(sesion, ahora=ahora)

    assert anonimizados == 3
    assert vigente.phone_e164 == "3001234567"
