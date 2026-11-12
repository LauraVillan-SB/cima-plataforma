"""Guardrails, validación de salida y transparencia del Agente Conversacional.

Funciones puras (sin E/S) que aplican IA responsable (Req 16):
- `evaluar_entrada`: bloquea contenido inseguro o fuera del dominio ANTES de
  invocar el modelo (Req 16.1). Recibe texto ya redactado de PII.
- `validar_salida`: si la respuesta menciona una oferta/incentivo, exige que el
  backend la respalde; si no, la deriva a respuesta segura (Req 16.2).
- `requiere_derivacion`: detecta tema sensible o baja confianza para derivar a
  canal humano / respuesta segura (Req 16.3).
- `marcar_como_ia`: antepone la indicación reconocible de IA (Req 16.5).

El kill switch (Req 16.6) y el registro auditable (Req 16.4) se aplican en el
servicio; aquí solo vive la lógica de decisión, para poder probarla aislada.
"""

from __future__ import annotations

import re

from app.chat.constants import (
    AI_DISCLOSURE_PREFIX,
    BLOCKED_INPUT_PATTERNS,
    GUARDRAIL_BLOQUEO_ENTRADA,
    GUARDRAIL_DERIVADO,
    GUARDRAIL_PERMITIDO,
    GUARDRAIL_SALIDA_NO_VALIDADA,
    CATALOG_BACKED_OFFER_MARKERS,
    OFFER_FIGURES_PATTERN,
    OFFER_OUTPUT_MARKERS,
    SENSITIVE_TOPIC_PATTERNS,
)
from app.conversion.catalog import normalizar_texto

_BLOCKED_INPUT = tuple(re.compile(p, re.IGNORECASE) for p in BLOCKED_INPUT_PATTERNS)
_SENSITIVE = tuple(re.compile(p, re.IGNORECASE) for p in SENSITIVE_TOPIC_PATTERNS)
_OFFER_FIGURES = re.compile(OFFER_FIGURES_PATTERN, re.IGNORECASE)


def _por_inicio_de_palabra(marcadores: tuple[str, ...]) -> re.Pattern[str]:
    """Une los marcadores (sin tildes) en un patrón que exige inicio de palabra.

    Por inicio de palabra y no como subcadena: "bono" no debe coincidir dentro de
    "abono", muy frecuente en respuestas para agricultores.
    """
    alternativas = "|".join(re.escape(normalizar_texto(m)) for m in marcadores)
    return re.compile(rf"\b(?:{alternativas})")


_OFERTA = _por_inicio_de_palabra(OFFER_OUTPUT_MARKERS)
_MARCADORES_NO_RESPALDABLES = _por_inicio_de_palabra(
    tuple(m for m in OFFER_OUTPUT_MARKERS if m not in CATALOG_BACKED_OFFER_MARKERS)
)


def evaluar_entrada(texto_redactado: str) -> str:
    """Evalúa la entrada del Usuario antes de invocar el modelo (Req 16.1).

    Args:
        texto_redactado: texto del Usuario, ya validado (11.1) y redactado (11.2).

    Returns:
        `GUARDRAIL_PERMITIDO` si la entrada puede ir al modelo, o
        `GUARDRAIL_BLOQUEO_ENTRADA` si contiene un patrón inseguro o fuera de dominio.
    """
    # Sin tildes, en minúsculas y con espacios colapsados: una transcripción con
    # tildes descompuestas (NFD) o MAYÚSCULAS no debe saltarse el guardrail.
    texto = normalizar_texto(texto_redactado)
    if any(patron.search(texto) for patron in _BLOCKED_INPUT):
        return GUARDRAIL_BLOQUEO_ENTRADA
    return GUARDRAIL_PERMITIDO


def validar_salida(respuesta: str, oferta_respaldada: bool) -> str:
    """Valida la salida del modelo contra las reglas de negocio (Req 16.2).

    Si la respuesta menciona una oferta o incentivo, solo se permite cuando el
    backend confirma que esa oferta está respaldada (`oferta_respaldada=True`).
    Así el agente no puede inventar ofertas ni beneficios no autorizados.

    Args:
        respuesta: texto generado por el modelo.
        oferta_respaldada: True si el backend validó una oferta vigente para el
            Usuario (coordinación con Conversion Service, Req 5.4).

    Returns:
        `GUARDRAIL_PERMITIDO` si la salida puede presentarse, o
        `GUARDRAIL_SALIDA_NO_VALIDADA` si menciona una oferta sin respaldo.
    """
    if menciona_oferta(respuesta) and not oferta_respaldada:
        return GUARDRAIL_SALIDA_NO_VALIDADA
    return GUARDRAIL_PERMITIDO


def requiere_derivacion(texto_redactado: str, confianza: float, umbral: float) -> str:
    """Determina si la interacción debe derivarse a canal humano (Req 16.3).

    Deriva cuando se detecta un tema sensible o cuando la confianza de la
    respuesta es inferior al umbral configurado.

    Args:
        texto_redactado: texto a inspeccionar (entrada o salida redactada).
        confianza: confianza de la respuesta del modelo en [0, 1].
        umbral: confianza mínima aceptable.

    Returns:
        `GUARDRAIL_DERIVADO` si debe derivarse, o `GUARDRAIL_PERMITIDO` si no.
    """
    if confianza < umbral:
        return GUARDRAIL_DERIVADO
    texto = normalizar_texto(texto_redactado)
    if any(patron.search(texto) for patron in _SENSITIVE):
        return GUARDRAIL_DERIVADO
    return GUARDRAIL_PERMITIDO


def marcar_como_ia(respuesta: str) -> str:
    """Antepone la indicación reconocible de que responde una IA (Req 16.5).

    Es idempotente: no duplica la marca si la respuesta ya la tiene.

    Args:
        respuesta: texto a presentar al Usuario.

    Returns:
        La respuesta con el prefijo de divulgación de IA.
    """
    if respuesta.startswith(AI_DISCLOSURE_PREFIX):
        return respuesta
    return AI_DISCLOSURE_PREFIX + respuesta


def oferta_respaldada_por_catalogo(
    respuesta: str,
    nombres_permitidos: frozenset[str],
    nombres_conocidos: frozenset[str],
) -> bool:
    """Indica si las ofertas de la respuesta están respaldadas por el catálogo (Req 16.2).

    Una respuesta sin oferta es válida. Con oferta, solo se respalda si solo
    habla de Microseguros del catálogo del Usuario: sin incentivos, descuentos
    ni cifras (el catálogo no tiene precios) y sin nombrar productos que no le
    corresponden por su tipo de actividad.

    Args:
        respuesta: texto generado por el modelo.
        nombres_permitidos: nombres normalizados de las ofertas del Usuario.
        nombres_conocidos: nombres normalizados de todas las ofertas del catálogo.

    Returns:
        True si la respuesta no ofrece nada o si todo lo que ofrece está respaldado.
    """
    if not menciona_oferta(respuesta):
        return True
    texto = normalizar_texto(respuesta)
    if _MARCADORES_NO_RESPALDABLES.search(texto):
        return False
    if not nombres_permitidos or _OFFER_FIGURES.search(texto):
        return False
    ajenos = nombres_conocidos - nombres_permitidos
    return not any(nombre in texto for nombre in ajenos)


def menciona_oferta(respuesta: str) -> bool:
    """Indica si la respuesta menciona una oferta o incentivo.

    Args:
        respuesta: texto generado por el modelo.

    Returns:
        True si alguna palabra empieza por un marcador de oferta (sin distinguir
        mayúsculas ni tildes).
    """
    return _OFERTA.search(normalizar_texto(respuesta)) is not None
