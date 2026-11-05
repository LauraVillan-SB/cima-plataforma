"""Esquemas (DTO) de salida del Tablero de Impacto ODS.

El tablero es de solo lectura y solo expone datos agregados y anonimizados
(Req 15.1, 15.3); ningún DTO contiene PII ni identificadores de Usuarios
individuales. Las zonas con menos de 5 Usuarios se suprimen aguas arriba
(Req 15.4).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ImpactMetric(BaseModel):
    """Una métrica de impacto agregada por zona, vinculada a su ODS (Req 15.1, 15.2)."""

    model_config = ConfigDict(frozen=True)

    event_type: str
    label: str
    ods: str
    geo_zone: str
    total: int
    distinct_users: int


class ImpactDashboard(BaseModel):
    """Tablero de Impacto: métricas agregadas por zona y ODS (Req 15.1–15.4).

    `metrics` ya trae aplicada la supresión por k-anonimato; si tras la supresión
    no queda ninguna fila, la lista viene vacía (sin datos que mostrar).
    """

    model_config = ConfigDict(frozen=True)

    metrics: list[ImpactMetric]
