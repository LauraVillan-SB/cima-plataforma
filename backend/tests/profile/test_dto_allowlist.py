"""Prueba de propiedad: DTO con allowlist en respuestas con datos del Perfil.

Feature: cima-plataforma, Property 32: DTO con allowlist en respuestas de Perfil.
Validates: Requirements 9.5 (y el enmascaramiento de Req 9.4).

*Para toda* respuesta de API que incluye datos del perfil, el conjunto de campos
expuestos es exactamente el del DTO autorizado, omitiendo cualquier otro campo.
Se genera un Perfil arbitrario que también trae los campos internos que nunca
deben salir (`clave_hash`, `role`, `failed_attempts`, `locked_until`,
`created_at`) y se verifica la respuesta de consultar y actualizar el Perfil y la
de ingresar. Además se fija el contrato OpenAPI de esos endpoints, que es lo que
FastAPI usa para filtrar la respuesta (`response_model`).

No usan BD real: una sesión en memoria simula `get`/`scalar`/`commit`/`refresh`.
"""
from __future__ import annotations

import json
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth import service as auth_service
from app.auth.dto import IngresoRequest
from app.auth.password import hash_clave
from app.profile import service as profile_service
from app.profile.constants import ALLOWED_ACTIVITY_TYPES
from app.profile.dto import ProfileUpdate
from app.profile.models import Profile

# Campos autorizados por DTO (allowlist). Cualquier otro campo es una fuga.
CAMPOS_PERFIL = {"id", "phone", "activity_type", "geo_zone"}
CAMPOS_SESION = {"id", "telefono"}

# Campos internos del modelo que jamás deben aparecer en una respuesta.
CAMPOS_INTERNOS = {
    "phone_e164",
    "clave_hash",
    "role",
    "failed_attempts",
    "locked_until",
    "created_at",
}

_CLAVE = "1234"
# El hash se calcula una sola vez: bcrypt es lento a propósito.
_HASH_CLAVE = hash_clave(_CLAVE)
_VISIBLES = 4


class _FakeSession:
    """Sesión async mínima que siempre devuelve el Perfil sembrado."""

    def __init__(self, profile: Profile) -> None:
        self._profile = profile

    async def get(self, _model, _pk) -> Profile:
        return self._profile

    async def scalar(self, _stmt) -> Profile:
        return self._profile

    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


# --------------------------------------------------------------------------- #
# Estrategias
# --------------------------------------------------------------------------- #
_telefonos = st.text(alphabet=string.digits, min_size=7, max_size=15)
_actividades = st.sampled_from(sorted(ALLOWED_ACTIVITY_TYPES))
_zonas = (
    st.text(alphabet=string.ascii_letters + " -", min_size=1, max_size=100)
    .map(str.strip)
    .filter(bool)
)
# Hash con forma bcrypt y cuerpo aleatorio: difícil que aparezca por azar.
_hashes = st.text(
    alphabet=string.ascii_letters + string.digits, min_size=53, max_size=53
).map(lambda cuerpo: f"$2b$12${cuerpo}")
_bloqueos = st.one_of(
    st.none(),
    st.integers(min_value=-86_400, max_value=-1).map(
        lambda s: datetime.now(timezone.utc) + timedelta(seconds=s)
    ),
)


@st.composite
def _perfiles(draw: st.DrawFn, clave_hash: str | None = None) -> Profile:
    """Perfil arbitrario con todos sus campos, incluidos los internos."""
    return Profile(
        id=uuid.uuid4(),
        phone_e164=draw(_telefonos),
        clave_hash=clave_hash if clave_hash is not None else draw(_hashes),
        activity_type=draw(_actividades),
        geo_zone=draw(_zonas),
        role=draw(st.sampled_from(["usuario", "admin"])),
        failed_attempts=draw(st.integers(min_value=0, max_value=4)),
        locked_until=draw(_bloqueos),
        created_at=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------- #
# Verificaciones comunes
# --------------------------------------------------------------------------- #
def _assert_enmascarado(expuesto: str, original: str) -> None:
    """Solo quedan visibles los últimos 4 caracteres; el resto son asteriscos."""
    assert len(expuesto) == len(original)
    assert expuesto.endswith(original[-_VISIBLES:])
    assert set(expuesto[:-_VISIBLES]) <= {"*"}
    assert original not in expuesto


def _assert_sin_fugas(cuerpo: dict, perfil: Profile, campos: set[str]) -> None:
    """Exactamente los campos del DTO; ningún campo ni valor interno en el JSON."""
    assert set(cuerpo) == campos
    assert not (set(cuerpo) & CAMPOS_INTERNOS)
    serializado = json.dumps(cuerpo, default=str)
    assert perfil.clave_hash not in serializado
    # El celular completo no aparece en ningún campo distinto del id.
    sin_id = json.dumps({k: v for k, v in cuerpo.items() if k != "id"}, default=str)
    assert perfil.phone_e164 not in sin_id


# --------------------------------------------------------------------------- #
# Property 32
# --------------------------------------------------------------------------- #
# Feature: cima-plataforma, Property 32: DTO con allowlist en respuestas de Perfil.
# Validates: Requirements 9.5
@settings(max_examples=100, deadline=None)
@given(perfil=_perfiles())
@pytest.mark.asyncio
async def test_property_32_consultar_perfil_expone_solo_la_allowlist(perfil: Profile) -> None:
    respuesta = await profile_service.get_own_profile(_FakeSession(perfil), perfil.id)

    cuerpo = respuesta.model_dump(mode="json")
    _assert_sin_fugas(cuerpo, perfil, CAMPOS_PERFIL)
    _assert_enmascarado(cuerpo["phone"], perfil.phone_e164)


# Feature: cima-plataforma, Property 32: DTO con allowlist en respuestas de Perfil.
# Validates: Requirements 9.5
@settings(max_examples=100, deadline=None)
@given(perfil=_perfiles(), actividad=_actividades, zona=_zonas)
@pytest.mark.asyncio
async def test_property_32_actualizar_perfil_expone_solo_la_allowlist(
    perfil: Profile, actividad: str, zona: str
) -> None:
    datos = ProfileUpdate(activity_type=actividad, geo_zone=zona)
    respuesta = await profile_service.update_own_profile(
        db=_FakeSession(perfil),
        current_user_id=perfil.id,
        target_id=perfil.id,
        data=datos,
    )

    cuerpo = respuesta.model_dump(mode="json")
    _assert_sin_fugas(cuerpo, perfil, CAMPOS_PERFIL)
    _assert_enmascarado(cuerpo["phone"], perfil.phone_e164)


# Feature: cima-plataforma, Property 32: DTO con allowlist en respuestas de Perfil.
# Validates: Requirements 9.5
@settings(max_examples=100, deadline=None)
@given(perfil=_perfiles(clave_hash=_HASH_CLAVE))
@pytest.mark.asyncio
async def test_property_32_ingresar_expone_solo_la_allowlist(perfil: Profile) -> None:
    # Bloqueo ya vencido (o ninguno) y contador bajo el umbral: el ingreso procede.
    respuesta = await auth_service.ingresar(
        _FakeSession(perfil),
        IngresoRequest(telefono=perfil.phone_e164, clave=_CLAVE),
    )

    cuerpo = respuesta.model_dump(mode="json")
    _assert_sin_fugas(cuerpo, perfil, CAMPOS_SESION)
    _assert_enmascarado(cuerpo["telefono"], perfil.phone_e164)


# --------------------------------------------------------------------------- #
# Contrato OpenAPI: FastAPI filtra la respuesta con estos esquemas.
# --------------------------------------------------------------------------- #
def _propiedades_respuesta(openapi: dict, ruta: str, metodo: str, codigo: str) -> set[str]:
    contenido = openapi["paths"][ruta][metodo]["responses"][codigo]["content"]
    ref = contenido["application/json"]["schema"]["$ref"]
    nombre = ref.rsplit("/", 1)[-1]
    return set(openapi["components"]["schemas"][nombre]["properties"])


@pytest.mark.parametrize(
    ("ruta", "metodo", "codigo", "campos"),
    [
        ("/api/v1/perfiles/me", "get", "200", CAMPOS_PERFIL),
        ("/api/v1/perfiles/{perfil_id}", "put", "200", CAMPOS_PERFIL),
        ("/api/v1/auth/registro", "post", "201", CAMPOS_SESION),
        ("/api/v1/auth/ingreso", "post", "200", CAMPOS_SESION),
        ("/api/v1/auth/refresco", "post", "200", CAMPOS_SESION),
        ("/api/v1/auth/sesion", "get", "200", CAMPOS_SESION),
    ],
)
def test_property_32_contrato_openapi_solo_declara_la_allowlist(
    ruta: str, metodo: str, codigo: str, campos: set[str]
) -> None:
    from app.main import app

    assert _propiedades_respuesta(app.openapi(), ruta, metodo, codigo) == campos
