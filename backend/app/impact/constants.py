"""Constantes de dominio del Tablero de Impacto ODS (Req 15).

Mapea cada tipo de evento de métrica al Objetivo de Desarrollo Sostenible (ODS)
pertinente (Req 15.2): ODS 8 (trabajo decente y crecimiento económico), ODS 10
(reducción de las desigualdades) y ODS 13 (acción por el clima). El tablero se
calcula solo sobre datos agregados y anonimizados (Req 15.3), reutilizando el
umbral de k-anonimato del Metrics Service (Req 15.4).
"""

from __future__ import annotations

# ODS pertinentes al impacto de CIMA (Req 15.2).
ODS_8 = "ODS 8"
ODS_10 = "ODS 10"
ODS_13 = "ODS 13"

# Mapeo de cada tipo de evento de métrica al ODS que representa (Req 15.2):
# - microcápsulas completadas → formación/empleabilidad → ODS 8.
# - rutas completadas → inclusión y reducción de brechas → ODS 10.
# - activación de microseguros → protección ante el clima → ODS 13.
EVENT_TYPE_TO_ODS: dict[str, str] = {
    "microcapsula_completada": ODS_8,
    "ruta_completada": ODS_10,
    "conversion_microseguro": ODS_13,
}

# Etiqueta legible de cada métrica de impacto para presentación en el tablero.
EVENT_TYPE_LABEL: dict[str, str] = {
    "microcapsula_completada": "Microcápsulas completadas",
    "ruta_completada": "Rutas de aprendizaje completadas",
    "conversion_microseguro": "Microseguros activados",
}
