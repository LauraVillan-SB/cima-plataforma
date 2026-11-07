"""Esquemas (DTO) del Gamification Service.

`RecognitionGrantResult` es el resultado de un otorgamiento. Lo devuelve el
servicio a quien lo invoca dentro del backend (el Learning Service, Tarea 13.3).
No hay un DTO de entrada expuesto a clientes: el otorgamiento no se acepta desde
el cliente porque permitiría darse reconocimientos sin completar nada
(Req 19.3). El resultado no contiene PII.
Requisitos: 19.1, 19.2, 19.3.
"""

from __future__ import annotations

from typing import Optional

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


class LevelOut(BaseModel):
    """Nivel del titular, derivado de sus puntos (no se guarda)."""

    model_config = ConfigDict(frozen=True)

    number: int
    name: str
    min_points: int


class NextLevelOut(BaseModel):
    """Siguiente nivel y cuántos puntos faltan para alcanzarlo."""

    model_config = ConfigDict(frozen=True)

    number: int
    name: str
    points_needed: int


class BadgeStatusOut(BaseModel):
    """Una Insignia del catálogo con indicación de si el titular ya la tiene."""

    model_config = ConfigDict(frozen=True)

    badge_code: str
    badge_name: str
    points: int
    earned: bool


class GamificationSummary(BaseModel):
    """Resumen de gamificación del titular autenticado.

    Puntos, nivel, racha e Insignias (con las que aún no tiene marcadas). Allowlist
    de campos: sin identificador del Perfil ni PII. Nivel y racha son una extensión
    de experiencia no especificada en requirements.md; las reglas viven en el backend.
    """

    model_config = ConfigDict(frozen=True)

    total_points: int
    streak_days: int
    level: LevelOut
    next_level: Optional[NextLevelOut]
    level_progress_pct: int
    badges: list[BadgeStatusOut]


class LeaderboardEntry(BaseModel):
    """Fila del ranking. El alias es seudónimo: no hay nombre, teléfono ni id real."""

    model_config = ConfigDict(frozen=True)

    rank: int
    alias: str
    total_points: int
    level_name: str
    streak_days: int
    is_me: bool


class Leaderboard(BaseModel):
    """Ranking acotado (top N) y la posición del titular aunque quede fuera del top."""

    model_config = ConfigDict(frozen=True)

    entries: list[LeaderboardEntry]
    me: Optional[LeaderboardEntry]
    participants: int
