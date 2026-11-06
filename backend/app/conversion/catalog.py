"""Consulta pura del catálogo de Microseguros (sin E/S).

Expone los nombres de las ofertas respaldadas por el catálogo para que otros
servicios (p. ej. los guardrails del Conversational Agent, Req 16.2) validen si
una oferta mencionada existe realmente para el Usuario.

Requisitos: 5.4, 16.2.
"""

from __future__ import annotations

import unicodedata

from app.conversion.constants import MICROINSURANCE_CATALOG


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparar: minúsculas, sin tildes y sin espacios extra.

    Args:
        texto: texto a normalizar.

    Returns:
        El texto en minúsculas, sin diacríticos y con espacios colapsados.
    """
    descompuesto = unicodedata.normalize("NFKD", texto.lower())
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.split())


def nombres_de_ofertas(activity_type: str) -> frozenset[str]:
    """Nombres normalizados de las ofertas del catálogo para un tipo de actividad.

    Args:
        activity_type: tipo de cultivo o comercio del Perfil.

    Returns:
        Conjunto de nombres normalizados; vacío si no hay oferta (Req 5.8).
    """
    opciones = MICROINSURANCE_CATALOG.get(activity_type, [])
    return frozenset(normalizar_texto(opcion["nombre"]) for opcion in opciones)


def nombres_de_todas_las_ofertas() -> frozenset[str]:
    """Nombres normalizados de todas las ofertas conocidas del catálogo.

    Returns:
        Conjunto con los nombres de todos los tipos de actividad.
    """
    return frozenset(
        normalizar_texto(opcion["nombre"])
        for opciones in MICROINSURANCE_CATALOG.values()
        for opcion in opciones
    )
