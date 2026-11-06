"""Fixtures compartidas de las pruebas del Learning Service.

Aíslan el otorgamiento de reconocimientos: las pruebas de Learning usan una sesión
simulada que no sabe responder a las consultas de Gamification, por lo que
`grant_recognition` se reemplaza por un registro de llamadas. El comportamiento real
de Gamification se prueba en `tests/gamification`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class GrantCall:
    """Llamada registrada a `grant_recognition`."""

    profile_id: uuid.UUID
    trigger: str
    client_event_id: uuid.UUID


@pytest.fixture(autouse=True)
def grants(monkeypatch: pytest.MonkeyPatch) -> list[GrantCall]:
    """Reemplaza `grant_recognition` por un registro de las llamadas recibidas."""
    calls: list[GrantCall] = []

    async def _fake_grant(db, profile_id, trigger, client_event_id):  # noqa: ANN001, ANN202
        calls.append(GrantCall(profile_id, trigger, client_event_id))

    monkeypatch.setattr("app.gamification.service.grant_recognition", _fake_grant)
    return calls
