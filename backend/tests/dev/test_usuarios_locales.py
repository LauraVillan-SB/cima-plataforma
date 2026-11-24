"""Pruebas del script que deja listos los usuarios de prueba locales.

Usa una sesión falsa: no toca la base de datos.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.auth.password import verify_clave
from app.dev import usuarios_locales as modulo
from app.dev.usuarios_locales import USUARIOS, UsuarioLocal, asegurar_usuario, asegurar_usuarios
from app.profile.models import Profile


class _SesionFalsa:
    """Guarda los Perfiles en memoria y cuenta los commits."""

    def __init__(self, existentes: list[Profile] | None = None) -> None:
        self.perfiles = {p.phone_e164: p for p in existentes or []}
        self.commits = 0

    async def scalar(self, consulta):  # noqa: ANN001, ANN201
        telefono = consulta.whereclause.right.value
        return self.perfiles.get(telefono)

    def add(self, perfil: Profile) -> None:
        self.perfiles[perfil.phone_e164] = perfil

    async def flush(self) -> None:
        for perfil in self.perfiles.values():
            perfil.id = perfil.id or uuid.uuid4()

    async def commit(self) -> None:
        self.commits += 1


def test_son_patricia_del_cafe_y_rosa_tendera() -> None:
    """Siempre hay una agricultora de café y una tendera (pyme)."""
    assert [(u.nombre, u.actividad) for u in USUARIOS] == [
        ("Patricia", "cafe"),
        ("Rosa Ruiz", "tienda_barrio"),
    ]
    assert len({u.telefono for u in USUARIOS}) == len(USUARIOS)


async def test_crea_los_usuarios_con_la_clave_solo_como_hash() -> None:
    sesion = _SesionFalsa()
    resultados = await asegurar_usuarios(sesion, "4826")

    assert sesion.commits == 1
    assert all(r.creado for r in resultados)
    for usuario in USUARIOS:
        perfil = sesion.perfiles[usuario.telefono]
        assert perfil.clave_hash != "4826"
        assert verify_clave("4826", perfil.clave_hash)
        assert (perfil.activity_type, perfil.geo_zone) == (usuario.actividad, usuario.zona)


async def test_si_ya_existe_lo_actualiza_y_le_quita_el_bloqueo() -> None:
    existente = Profile(
        phone_e164=USUARIOS[1].telefono,
        clave_hash="hash-viejo",
        activity_type="",
        geo_zone="",
        failed_attempts=5,
        locked_until=datetime.now(timezone.utc),
    )
    sesion = _SesionFalsa([existente])

    resultado = await asegurar_usuario(sesion, USUARIOS[1], "1593")

    assert not resultado.creado
    assert sesion.perfiles[USUARIOS[1].telefono] is existente
    assert existente.failed_attempts == 0 and existente.locked_until is None
    assert existente.activity_type == "tienda_barrio"
    assert verify_clave("1593", existente.clave_hash)


async def test_no_muestra_el_celular_completo() -> None:
    resultado = await asegurar_usuario(_SesionFalsa(), USUARIOS[0], "4826")
    assert USUARIOS[0].telefono not in resultado.telefono_enmascarado
    assert resultado.telefono_enmascarado.endswith(USUARIOS[0].telefono[-4:])


async def test_rechaza_una_actividad_fuera_de_la_allowlist() -> None:
    with pytest.raises(ValueError):
        await asegurar_usuario(_SesionFalsa(), UsuarioLocal("X", "3000000009", "mineria", "Z"), "1234")


@pytest.mark.parametrize("entorno", ["prod", "production", "stage"])
def test_no_corre_fuera_de_desarrollo(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    monkeypatch.setattr(modulo, "get_settings", lambda: SimpleNamespace(app_env=entorno))
    monkeypatch.setenv(modulo.VARIABLE_CLAVE, "1234")
    assert modulo.main() == 1


@pytest.mark.parametrize("clave", ["", "123", "12345", "abcd"])
def test_exige_una_clave_de_cuatro_digitos(monkeypatch: pytest.MonkeyPatch, clave: str) -> None:
    monkeypatch.setattr(modulo, "get_settings", lambda: SimpleNamespace(app_env="dev"))
    monkeypatch.setenv(modulo.VARIABLE_CLAVE, clave)
    assert modulo.main() == 1
