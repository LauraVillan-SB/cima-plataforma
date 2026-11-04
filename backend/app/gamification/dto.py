"""Esquemas (DTO) del Gamification Service.

`RecognitionGrantResult` es el resultado de un otorgamiento. Lo devuelve el
servicio a quien lo invoca dentro del backend (el Learning Service, Tarea 13.3).
No hay un DTO de entrada expuesto a clientes: el otorgamiento no se acepta desde
el cliente porque permitiría darse reconocimientos sin completar nada
(Req 19.3). El resultado no contiene PII.
Requisitos: 19.1, 19.2, 19.3.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RecognitionGrantResult(BaseModel):
    """Resultado de un otorgamiento; sin PII (Req 19.2).

    `newly_awarded` es False cuando la Insignia ya existía (idempotencia,
    Req 19.5): en ese caso `total_points` no cambia.
    """

    model_config = ConfigDict(frozen=True)

    badge_code: str
    badge_name: str
    total_points: int
    newly_awarded: bool


class BadgeOut(BaseModel):
    """Insignia dentro del listado de reconocimientos del titular (Req 19.7)."""

    model_config = ConfigDict(frozen=True)

    badge_code: str
    badge_name: str


class RecognitionSummary(BaseModel):
    """Insignias y total de puntos del titular autenticado (Req 19.7).

    Allowlist de campos: no incluye el identificador del Perfil ni PII, de modo
    que la respuesta no revela nada de otros Perfiles (Req 19.8).
    """

    model_config = ConfigDict(frozen=True)

    badges: list[BadgeOut]
    total_points: int
