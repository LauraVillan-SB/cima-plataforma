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
    OFFER_OUTPUT_MARKERS,
    SENSITIVE_TOPIC_PATTERNS,
)

_BLOCKED_INPUT = tuple(re.compile(p, re.IGNORECASE) for p in BLOCKED_INPUT_PATTERNS)
_SENSITIVE = tuple(re.compile(p, re.IGNORECASE) for p in SENSITIVE_TOPIC_PATTERNS)


def evaluar_entrada(texto_redactado: str) -> str:
    """Evalúa la entrada del Usuario antes de invocar el modelo (Req 16.1).

    Args:
        texto_redactado: texto del Usuario, ya validado (11.1) y redactado (11.2).

    Returns:
        `GUARDRAIL_PERMITIDO` si la entrada puede ir al modelo, o
        `GUARDRAIL_BLOQUEO_ENTRADA` si contiene un patrón inseguro o fuera de dominio.
    """
    if any(patron.search(texto_redactado) for patron in _BLOCKED_INPUT):
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
    menciona_oferta = _menciona_oferta(respuesta)
    if menciona_oferta and not oferta_respaldada:
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
    if any(patron.search(texto_redactado) for patron in _SENSITIVE):
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


def _menciona_oferta(respuesta: str) -> bool:
    """Indica si la respuesta menciona una oferta o incentivo.

    Args:
        respuesta: texto generado por el modelo.

    Returns:
        True si contiene algún marcador de oferta (comparación sin distinguir
        mayúsculas).
    """
    minuscula = respuesta.lower()
    return any(marcador in minuscula for marcador in OFFER_OUTPUT_MARKERS)
