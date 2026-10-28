"""Pruebas del bloqueo por intentos, reactivación y cambio de Clave del Auth Service.

Feature: cima-plataforma, Property 4: Bloqueo por intentos fallidos consecutivos.
Feature: cima-plataforma, Property 5: Reactivación tras expirar el bloqueo.

No usan BD real: un stub de sesión en memoria simula scalar/get/commit. El reloj
se controla fijando `locked_until` para no depender del tiempo real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth import service
from app.auth.dto import CambioClaveRequest, IngresoRequest
from app.auth.password import hash_clave
from app.common.config import get_settings
from app.common.errors import CredencialesInvalidasError, CuentaBloqueadaError
from app.profile.models import Profile

_TELEFONO = "3001234567"
_CLAVE_OK = "1234"
_CLAVE_MALA = "9999"
_MAX = get_settings().max_failed_attempts
_LOCKOUT = get_settings().lockout_seconds


class _FakeSession:
    """Sesión async mínima: `scalar` por teléfono y `get` por id."""

    def __init__(self, stored: Profile | None = None) -> None:
        self.stored = stored
        self.commits = 0

    async def scalar(self, _stmt) -> Profile | None:
        return self.stored

    async def get(self, _model, _pk) -> Profile | None:
        return self.stored

    async def commit(self) -> None:
        self.commits += 1


def _perfil(clave: str = _CLAVE_OK, failed: int = 0, locked_until=None) -> Profile:
    return Profile(
        id=uuid.uuid4(),
        phone_e164=_TELEFONO,
        clave_hash=hash_clave(clave),
        activity_type="",
        geo_zone="",
        failed_attempts=failed,
        locked_until=locked_until,
    )


# Feature: cima-plataforma, Property 4: Bloqueo por intentos fallidos consecutivos.
# Validates: Requirements 1.11
@settings(max_examples=100, deadline=None)
@given(fallos_previos=st.integers(min_value=0, max_value=_MAX - 1))
@pytest.mark.asyncio
async def test_property_4_bloqueo_tras_umbral_de_fallos(fallos_previos: int) -> None:
    """Con < umbral no hay bloqueo; al alcanzar el umbral se bloquea el siguiente intento."""
    perfil = _perfil(failed=fallos_previos)
    sesion = _FakeSession(stored=perfil)

    # When falla un ingreso con Clave incorrecta
    with pytest.raises(CredencialesInvalidasError):
        await service.ingresar(sesion, IngresoRequest(telefono=_TELEFONO, clave=_CLAVE_MALA))

    # Then el contador se incrementó en 1
    assert perfil.failed_attempts == fallos_previos + 1
    # And se fija el bloqueo si y solo si se alcanzó el umbral (Req 1.12)
    if perfil.failed_attempts >= _MAX:
        assert perfil.locked_until is not None
    else:
        assert perfil.locked_until is None


@pytest.mark.asyncio
async def test_property_4_ingreso_exitoso_reinicia_el_contador() -> None:
    """Un ingreso exitoso reinicia el conteo de fallos a cero (Req 1.11)."""
    perfil = _perfil(clave=_CLAVE_OK, failed=_MAX - 1)
    sesion = _FakeSession(stored=perfil)
    await service.ingresar(sesion, IngresoRequest(telefono=_TELEFONO, clave=_CLAVE_OK))
    assert perfil.failed_attempts == 0
    assert perfil.locked_until is None


@pytest.mark.asyncio
async def test_bloqueo_vigente_rechaza_con_cuenta_bloqueada() -> None:
    """Con un bloqueo vigente, el ingreso se rechaza con CuentaBloqueadaError (429)."""
    futuro = datetime.now(timezone.utc) + timedelta(seconds=_LOCKOUT)
    perfil = _perfil(clave=_CLAVE_OK, failed=_MAX, locked_until=futuro)
    sesion = _FakeSession(stored=perfil)
    # Incluso con la Clave correcta, el bloqueo vigente tiene prioridad.
    with pytest.raises(CuentaBloqueadaError):
        await service.ingresar(sesion, IngresoRequest(telefono=_TELEFONO, clave=_CLAVE_OK))


# Feature: cima-plataforma, Property 5: Reactivación tras expirar el bloqueo.
# Validates: Requirements 1.12
@pytest.mark.asyncio
async def test_property_5_reactivacion_tras_expirar_el_bloqueo() -> None:
    """Pasado el tiempo de bloqueo, un ingreso correcto reactiva la cuenta con contador en cero."""
    # Given un bloqueo ya expirado (locked_until en el pasado)
    pasado = datetime.now(timezone.utc) - timedelta(seconds=1)
    perfil = _perfil(clave=_CLAVE_OK, failed=_MAX, locked_until=pasado)
    sesion = _FakeSession(stored=perfil)

    # When ingresa con la Clave correcta tras expirar el bloqueo
    resp = await service.ingresar(sesion, IngresoRequest(telefono=_TELEFONO, clave=_CLAVE_OK))

    # Then el ingreso procede, el contador queda en cero y el bloqueo se limpia
    assert resp.id == perfil.id
    assert perfil.failed_attempts == 0
    assert perfil.locked_until is None


@pytest.mark.asyncio
async def test_cambiar_clave_exige_clave_actual() -> None:
    """El cambio de Clave requiere la Clave actual correcta (Req 1.15)."""
    perfil = _perfil(clave=_CLAVE_OK)
    sesion = _FakeSession(stored=perfil)
    hash_original = perfil.clave_hash

    # Clave actual incorrecta -> rechazo, sin cambiar el hash.
    with pytest.raises(CredencialesInvalidasError):
        await service.cambiar_clave(
            sesion,
            perfil.id,
            CambioClaveRequest(
                clave_actual=_CLAVE_MALA,
                clave_nueva="5678",
                confirmacion_clave_nueva="5678",
            ),
        )
    assert perfil.clave_hash == hash_original

    # Clave actual correcta -> se actualiza el hash.
    await service.cambiar_clave(
        sesion,
        perfil.id,
        CambioClaveRequest(
            clave_actual=_CLAVE_OK,
            clave_nueva="5678",
            confirmacion_clave_nueva="5678",
        ),
    )
    assert perfil.clave_hash != hash_original
