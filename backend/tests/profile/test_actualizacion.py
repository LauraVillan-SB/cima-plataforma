"""Pruebas de la actualización del Perfil propio (`ProfileUpdate`, Req 9.1, 9.2, 9.4).

Regresión: `PUT /api/v1/perfiles/{id}` exigía el teléfono (reutilizaba el esquema
de creación), pero el cliente solo conoce el celular ENMASCARADO (Req 9.4), por lo
que toda actualización respondía 422. Ahora la actualización solo admite el tipo
de cultivo/comercio y la zona; el teléfono no es editable por esa vía.

No usan BD real: una sesión en memoria simula `get`/`commit`/`refresh`.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.common.errors import NotFoundError
from app.profile import service
from app.profile.constants import GEO_ZONE_MAX_LENGTH
from app.profile.dto import ProfileUpdate
from app.profile.models import Profile


class _FakeSession:
    """Sesión async mínima: `get` devuelve el Perfil sembrado; el resto es no-op."""

    def __init__(self, profile: Profile | None) -> None:
        self._profile = profile
        self.commits = 0

    async def get(self, _model, _pk):
        return self._profile

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj) -> None:
        return None


def _perfil(profile_id: uuid.UUID) -> Profile:
    return Profile(
        id=profile_id,
        phone_e164="3001234567",
        clave_hash="hash-ficticio",
        activity_type="cafe",
        geo_zone="Huila",
    )


# --------------------------------------------------------------------------- #
# Esquema de entrada
# --------------------------------------------------------------------------- #
def test_actualizar_acepta_solo_actividad_y_zona_y_normaliza() -> None:
    dto = ProfileUpdate(activity_type="CAFE", geo_zone="  Huila  ")
    assert dto.activity_type == "cafe"  # se normaliza a minúsculas
    assert dto.geo_zone == "Huila"  # se recorta (trim)


def test_actualizar_rechaza_el_telefono_en_el_cuerpo() -> None:
    """El teléfono no es editable por esta vía: la allowlist lo rechaza (Req 9.1)."""
    payload = {"activity_type": "cafe", "geo_zone": "Huila", "phone": "3001234567"}
    with pytest.raises(PydanticValidationError):
        ProfileUpdate(**payload)


def test_actualizar_rechaza_actividad_fuera_de_allowlist() -> None:
    with pytest.raises(PydanticValidationError):
        ProfileUpdate(activity_type="mineria", geo_zone="Huila")


@pytest.mark.parametrize("zona", ["", "   ", "z" * (GEO_ZONE_MAX_LENGTH + 1)])
def test_actualizar_rechaza_zona_vacia_o_demasiado_larga(zona: str) -> None:
    with pytest.raises(PydanticValidationError):
        ProfileUpdate(activity_type="cafe", geo_zone=zona)


# --------------------------------------------------------------------------- #
# Servicio
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_actualizar_perfil_propio_aplica_cambios_y_enmascara_el_celular() -> None:
    uid = uuid.uuid4()
    perfil = _perfil(uid)
    sesion = _FakeSession(perfil)
    data = ProfileUpdate(activity_type="maiz", geo_zone="Tolima")

    respuesta = await service.update_own_profile(
        db=sesion, current_user_id=uid, target_id=uid, data=data
    )

    assert respuesta.activity_type == "maiz"
    assert respuesta.geo_zone == "Tolima"
    assert sesion.commits == 1
    # El celular no cambia y la respuesta lo entrega enmascarado (Req 9.4).
    assert perfil.phone_e164 == "3001234567"
    assert respuesta.phone.endswith("4567")
    assert "3001234567" not in respuesta.phone


@pytest.mark.asyncio
async def test_actualizar_perfil_inexistente_responde_no_encontrado() -> None:
    uid = uuid.uuid4()
    sesion = _FakeSession(None)
    data = ProfileUpdate(activity_type="cafe", geo_zone="Huila")

    with pytest.raises(NotFoundError):
        await service.update_own_profile(
            db=sesion, current_user_id=uid, target_id=uid, data=data
        )
    assert sesion.commits == 0
