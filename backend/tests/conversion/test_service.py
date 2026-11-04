"""Pruebas del Conversion Service (Tarea 16.2).

Cubren la oferta acotada de Microseguros por tipo de actividad (Req 5.4), el
registro de ausencia de oferta (Req 5.8), el registro idempotente de la
intención (Req 5.5, 5.6), la verificación anti-BOLA implícita (el titular sale
del Usuario autenticado) y el rechazo de opciones fuera del catálogo.

No usan BD real: un stub de sesión en memoria simula `get`, `scalar`, `add`,
`commit` y `refresh`. Todos los identificadores son ficticios.
"""
from __future__ import annotations

import uuid

import pytest

from app.common.errors import NotFoundError, ValidationError
from app.conversion import service
from app.conversion.constants import (
    MAX_MICROINSURANCE_OPTIONS,
    MICROINSURANCE_CATALOG,
)
from app.conversion.dto import ConversionIntentCreate
from app.conversion.models import ConversionIntent
from app.profile.models import Profile

_PATH_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _profile(activity_type: str, profile_id: uuid.UUID | None = None) -> Profile:
    """Crea un Perfil ficticio con el tipo de actividad indicado."""
    return Profile(
        id=profile_id or uuid.uuid4(),
        phone_e164="3001234567",
        clave_hash="hash",
        activity_type=activity_type,
        geo_zone="zona-1",
    )


class _FakeSession:
    """Sesión async mínima que simula el comportamiento del ORM en memoria.

    `get` devuelve el Perfil precargado si el id coincide; `scalar` busca una
    intención previa por `client_event_id`; `add`/`commit`/`refresh` registran
    el objeto y le asignan un id, como haría la BD.
    """

    def __init__(self, profile: Profile | None) -> None:
        self._profile = profile
        self.intents: list[ConversionIntent] = []
        self.added: list[object] = []
        self.commits = 0

    async def get(self, _model, pk):  # noqa: ANN001 - firma simplificada del stub
        if self._profile is not None and pk == self._profile.id:
            return self._profile
        return None

    async def scalar(self, _stmt):  # noqa: ANN001 - el stub ignora la query real
        # Devuelve la última intención agregada que ya tenga id (idempotencia).
        return self.intents[-1] if self.intents else None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: object) -> None:
        if isinstance(obj, ConversionIntent):
            if obj.id is None:
                obj.id = uuid.uuid4()
            self.intents.append(obj)


# --- Oferta de Microseguros (Req 5.4, 5.8) ---------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("activity_type", sorted(MICROINSURANCE_CATALOG.keys()))
async def test_oferta_acotada_entre_1_y_5_por_actividad(activity_type: str) -> None:
    """Cada tipo con catálogo ofrece entre 1 y 5 opciones del mismo tipo (Req 5.4)."""
    # Given un Perfil con un tipo de actividad del catálogo
    profile = _profile(activity_type)
    db = _FakeSession(profile)
    # When se construye la oferta
    offer = await service.build_offer(db, _PATH_ID, profile.id)
    # Then hay entre 1 y 5 opciones y corresponden al tipo del Perfil
    assert 1 <= len(offer.options) <= MAX_MICROINSURANCE_OPTIONS
    assert offer.activity_type == activity_type
    assert offer.path_id == _PATH_ID


@pytest.mark.asyncio
async def test_sin_oferta_devuelve_vacio_y_registra_ausencia() -> None:
    """Un tipo sin catálogo devuelve oferta vacía y registra la ausencia (Req 5.8)."""
    # Given un Perfil con un tipo sin opciones en el catálogo
    profile = _profile("desconocido")
    db = _FakeSession(profile)
    # When se construye la oferta
    offer = await service.build_offer(db, _PATH_ID, profile.id)
    # Then la oferta viene vacía y se registró un evento de ausencia sin PII
    assert offer.options == []
    assert db.commits == 1
    assert db.added and db.added[0].activity_type == "desconocido"


@pytest.mark.asyncio
async def test_oferta_falla_si_no_existe_perfil() -> None:
    """Sin Perfil del Usuario autenticado, la oferta no se construye."""
    db = _FakeSession(profile=None)
    with pytest.raises(NotFoundError):
        await service.build_offer(db, _PATH_ID, uuid.uuid4())


# --- Registro de la intención (Req 5.5, 5.6) --------------------------------


@pytest.mark.asyncio
async def test_registra_intencion_valida() -> None:
    """Una opción del catálogo del Perfil se registra con el titular autenticado."""
    # Given un Perfil de café y una opción válida de su catálogo
    profile = _profile("cafe")
    db = _FakeSession(profile)
    opcion = MICROINSURANCE_CATALOG["cafe"][0]["codigo"]
    data = ConversionIntentCreate(client_event_id=uuid.uuid4(), option_code=opcion)
    # When se registra la intención
    result = await service.record_intent(db, _PATH_ID, profile.id, data)
    # Then queda registrada con la opción seleccionada y para la ruta indicada
    assert result.registered is True
    assert result.option_code == opcion
    assert result.path_id == _PATH_ID
    assert db.intents[0].profile_id == profile.id


@pytest.mark.asyncio
async def test_rechaza_opcion_fuera_del_catalogo() -> None:
    """Una opción que no pertenece al tipo del Perfil se rechaza sin registrar."""
    # Given un Perfil de café y una opción de otro tipo
    profile = _profile("cafe")
    db = _FakeSession(profile)
    data = ConversionIntentCreate(
        client_event_id=uuid.uuid4(), option_code="ms_ganaderia_animal"
    )
    # When / Then se rechaza y no se persiste nada
    with pytest.raises(ValidationError):
        await service.record_intent(db, _PATH_ID, profile.id, data)
    assert db.intents == []


@pytest.mark.asyncio
async def test_registro_idempotente_por_client_event_id() -> None:
    """Reintentar con el mismo client_event_id no duplica la intención (Req 5.6)."""
    # Given una intención ya registrada
    profile = _profile("cafe")
    db = _FakeSession(profile)
    opcion = MICROINSURANCE_CATALOG["cafe"][0]["codigo"]
    data = ConversionIntentCreate(client_event_id=uuid.uuid4(), option_code=opcion)
    primero = await service.record_intent(db, _PATH_ID, profile.id, data)
    # When se reintenta con el mismo client_event_id
    segundo = await service.record_intent(db, _PATH_ID, profile.id, data)
    # Then devuelve la misma intención y no crea una nueva
    assert segundo.id == primero.id
    assert len(db.intents) == 1


@pytest.mark.asyncio
async def test_intencion_falla_si_no_existe_perfil() -> None:
    """Sin Perfil del Usuario autenticado, la intención no se registra."""
    db = _FakeSession(profile=None)
    data = ConversionIntentCreate(
        client_event_id=uuid.uuid4(), option_code="ms_cafe_clima"
    )
    with pytest.raises(NotFoundError):
        await service.record_intent(db, _PATH_ID, uuid.uuid4(), data)


# --- Validación del DTO de entrada ------------------------------------------


def test_dto_rechaza_campos_no_permitidos() -> None:
    """El DTO aplica allowlist: un `profile_id` del cliente se rechaza (anti-BOLA)."""
    from pydantic import ValidationError as PydValidationError

    with pytest.raises(PydValidationError):
        ConversionIntentCreate(
            client_event_id=uuid.uuid4(),
            option_code="ms_cafe_clima",
            profile_id=uuid.uuid4(),
        )


# --- Invariante del catálogo ------------------------------------------------


def test_catalogo_respeta_el_limite_de_opciones() -> None:
    """Ningún tipo del catálogo excede el máximo de opciones presentables (Req 5.4)."""
    for activity_type, opciones in MICROINSURANCE_CATALOG.items():
        assert 1 <= len(opciones) <= MAX_MICROINSURANCE_OPTIONS, activity_type


def test_codigos_de_opcion_son_unicos() -> None:
    """Los códigos de opción no se repiten entre tipos (evita ambigüedad al registrar)."""
    codigos = [
        opcion["codigo"]
        for opciones in MICROINSURANCE_CATALOG.values()
        for opcion in opciones
    ]
    assert len(codigos) == len(set(codigos))
