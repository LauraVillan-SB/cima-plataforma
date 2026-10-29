"""Pruebas del ingreso y registro del Auth Service.

Feature: cima-plataforma, Property 3: Error de ingreso indistinguible.

No usan BD real: un stub de sesión en memoria simula las operaciones del ORM
que consume el service (scalar/add/commit/refresh), aislando la lógica de
negocio. Las dependencias externas no se tocan en esta tarea.
"""
from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.auth import service
from app.auth.dto import IngresoRequest, RegistroRequest
from app.auth.password import hash_clave
from app.common.errors import CredencialesInvalidasError, ValidationError
from app.profile.models import Profile

_TELEFONO = "3001234567"
_claves = st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}")


class _FakeSession:
    """Sesión async mínima que simula el subconjunto del ORM usado por el service.

    `stored` representa el Perfil existente que devolverá `scalar` (o None si no
    hay ninguno). Registra los perfiles añadidos para poder inspeccionarlos.
    """

    def __init__(self, stored: Profile | None = None) -> None:
        self.stored = stored
        self.added: list[Profile] = []
        self.committed = False

    async def scalar(self, _stmt) -> Profile | None:
        return self.stored

    def add(self, obj: Profile) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Profile) -> None:
        # Simula la asignación de PK por la BD tras el insert.
        if obj.id is None:
            obj.id = uuid.uuid4()


def _perfil(telefono: str, clave: str) -> Profile:
    """Construye un Perfil con la Clave ya hasheada, como estaría en BD."""
    return Profile(
        id=uuid.uuid4(),
        phone_e164=telefono,
        clave_hash=hash_clave(clave),
        activity_type="",
        geo_zone="",
    )


# Feature: cima-plataforma, Property 3: Error de ingreso indistinguible.
# Validates: Requirements 1.7
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(clave_registrada=_claves, clave_intento=_claves)
@pytest.mark.asyncio
async def test_property_3_error_de_ingreso_indistinguible(
    clave_registrada: str, clave_intento: str
) -> None:
    """El error ante teléfono inexistente y Clave incorrecta es idéntico.

    Se comparan los dos caminos de fallo: (a) teléfono no registrado y (b)
    teléfono registrado con Clave incorrecta. Ambos deben producir la misma
    excepción, con el mismo código HTTP y el mismo mensaje público (Req 1.7).
    """
    # Caso (a): teléfono no registrado.
    sesion_sin_usuario = _FakeSession(stored=None)
    with pytest.raises(CredencialesInvalidasError) as err_no_existe:
        await service.ingresar(
            sesion_sin_usuario, IngresoRequest(telefono=_TELEFONO, clave=clave_intento)
        )

    # Caso (b): teléfono registrado pero con Clave incorrecta.
    otra = f"{(int(clave_registrada) + 1) % 10000:04d}"  # garantiza Clave distinta
    sesion_con_usuario = _FakeSession(stored=_perfil(_TELEFONO, clave_registrada))
    with pytest.raises(CredencialesInvalidasError) as err_clave_mala:
        await service.ingresar(
            sesion_con_usuario, IngresoRequest(telefono=_TELEFONO, clave=otra)
        )

    # Then: mismo código y mismo mensaje público en ambos casos (indistinguible).
    assert err_no_existe.value.status_code == err_clave_mala.value.status_code == 401
    assert err_no_existe.value.public_message == err_clave_mala.value.public_message


@pytest.mark.asyncio
async def test_ingreso_exitoso_devuelve_sesion_con_telefono_enmascarado() -> None:
    """Con credenciales correctas, el ingreso devuelve el id y el teléfono enmascarado."""
    sesion = _FakeSession(stored=_perfil(_TELEFONO, "1234"))
    resp = await service.ingresar(sesion, IngresoRequest(telefono=_TELEFONO, clave="1234"))
    # El teléfono nunca se expone en claro (Req 9.4): solo los últimos 4 dígitos.
    assert resp.telefono == "******4567"
    assert resp.telefono != _TELEFONO


@pytest.mark.asyncio
async def test_registro_rechaza_telefono_ya_existente() -> None:
    """El registro de un teléfono ya registrado se rechaza con ValidationError."""
    sesion = _FakeSession(stored=_perfil(_TELEFONO, "1234"))
    data = RegistroRequest(telefono=_TELEFONO, clave="1234", confirmacion_clave="1234")
    with pytest.raises(ValidationError):
        await service.registrar(sesion, data)


@pytest.mark.asyncio
async def test_registro_exitoso_hashea_la_clave_y_no_la_guarda_en_claro() -> None:
    """El registro almacena la Clave como hash con sal, nunca en texto plano (Req 1.5)."""
    sesion = _FakeSession(stored=None)
    data = RegistroRequest(telefono=_TELEFONO, clave="1234", confirmacion_clave="1234")
    resp = await service.registrar(sesion, data)
    # Se persistió exactamente un perfil con la Clave hasheada.
    assert len(sesion.added) == 1
    guardado = sesion.added[0]
    assert guardado.clave_hash != "1234"
    assert sesion.committed is True
    assert resp.telefono == "******4567"
