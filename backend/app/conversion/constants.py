"""Constantes de dominio del Conversion Service.

Catálogo estático de opciones de Microseguro por tipo de cultivo o comercio
(Req 5.4). CIMA no vende ni emite pólizas: el catálogo es solo contenido de
referencia para presentar opciones y registrar la intención del Usuario, sin
precios ni emisión. Las claves son los tipos de actividad del Perfil
(`ALLOWED_ACTIVITY_TYPES`); cualquier otra se trata como sin oferta (Req 5.8).

Si en el futuro el negocio necesita editar el catálogo sin desplegar código,
puede migrarse a una tabla sin cambiar el contrato de la API.
Requisitos: 5.4, 5.8.
"""

from __future__ import annotations

from typing import TypedDict


class MicroinsuranceOption(TypedDict):
    """Opción de Microseguro de referencia (sin precio ni emisión)."""

    codigo: str
    nombre: str
    descripcion: str


# Máximo de opciones presentables por tipo de actividad (Req 5.4).
MAX_MICROINSURANCE_OPTIONS = 5

# Catálogo estático por tipo de cultivo o comercio. Cada lista debe tener entre
# 1 y MAX_MICROINSURANCE_OPTIONS opciones (invariante verificado en pruebas).
MICROINSURANCE_CATALOG: dict[str, list[MicroinsuranceOption]] = {
    "cafe": [
        {
            "codigo": "ms_cafe_clima",
            "nombre": "Protección climática para café",
            "descripcion": "Respaldo ante heladas, exceso de lluvia o sequía en el cultivo de café.",
        },
        {
            "codigo": "ms_cafe_cosecha",
            "nombre": "Amparo de cosecha",
            "descripcion": "Apoyo económico si se pierde parte de la cosecha por eventos climáticos.",
        },
    ],
    "platano": [
        {
            "codigo": "ms_platano_viento",
            "nombre": "Protección contra vientos",
            "descripcion": "Respaldo ante daños por vientos fuertes en plataneras.",
        },
    ],
    "aguacate": [
        {
            "codigo": "ms_aguacate_clima",
            "nombre": "Protección climática para aguacate",
            "descripcion": "Respaldo ante sequías o lluvias extremas en el cultivo de aguacate.",
        },
    ],
    "cacao": [
        {
            "codigo": "ms_cacao_clima",
            "nombre": "Protección climática para cacao",
            "descripcion": "Respaldo ante eventos climáticos que afecten el cultivo de cacao.",
        },
    ],
    "arroz": [
        {
            "codigo": "ms_arroz_inundacion",
            "nombre": "Protección contra inundación",
            "descripcion": "Apoyo ante pérdidas por inundación en cultivos de arroz.",
        },
    ],
    "maiz": [
        {
            "codigo": "ms_maiz_clima",
            "nombre": "Protección climática para maíz",
            "descripcion": "Respaldo ante sequía o exceso de lluvia en el cultivo de maíz.",
        },
    ],
    "ganaderia": [
        {
            "codigo": "ms_ganaderia_animal",
            "nombre": "Amparo del ganado",
            "descripcion": "Apoyo económico ante la muerte de animales por causas cubiertas.",
        },
        {
            "codigo": "ms_ganaderia_sequia",
            "nombre": "Protección por sequía",
            "descripcion": "Respaldo ante falta de pasto y agua por sequías prolongadas.",
        },
    ],
    "hortalizas": [
        {
            "codigo": "ms_hortalizas_clima",
            "nombre": "Protección climática para hortalizas",
            "descripcion": "Respaldo ante eventos climáticos en cultivos de hortalizas.",
        },
    ],
    "tienda_barrio": [
        {
            "codigo": "ms_tienda_contenido",
            "nombre": "Protección del negocio",
            "descripcion": "Respaldo del inventario y enseres de la tienda ante imprevistos.",
        },
    ],
    "panaderia": [
        {
            "codigo": "ms_panaderia_equipo",
            "nombre": "Protección de equipos",
            "descripcion": "Apoyo ante daños a hornos y equipos de la panadería.",
        },
    ],
    "miscelanea": [
        {
            "codigo": "ms_miscelanea_contenido",
            "nombre": "Protección del negocio",
            "descripcion": "Respaldo del inventario de la miscelánea ante imprevistos.",
        },
    ],
    "fruteria": [
        {
            "codigo": "ms_fruteria_contenido",
            "nombre": "Protección del negocio",
            "descripcion": "Respaldo de mercancía perecedera y enseres de la frutería.",
        },
    ],
}
