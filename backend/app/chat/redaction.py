"""Redacción de PII antes de enviar contenido al modelo de IA generativa.

Se aplica al texto escrito por el Usuario y a la transcripción de una Nota de
Voz (Req 3.10, 14.6). Sustituye cada PII detectada por un marcador neutro
(`[TELEFONO]`, `[CORREO]`, ...) y luego verifica que no quede PII detectable.
Si la verificación falla, lanza `RedaccionPiiError` y el contenido no debe
enviarse al modelo (Req 3.11, Property 9).

Detecta: correos, direcciones colombianas (Calle/Carrera/... # N-N),
coordenadas, nombres tras "me llamo" / "mi nombre es", y secuencias de 6 o más
dígitos (celulares, cédulas, cuentas). Los montos con "$" o seguidos de
"pesos"/"mil"/"millones" se conservan porque son necesarios para la educación
financiera. Es un detector por patrones: no reconoce nombres sin frase
introductoria ni nombres de municipios o veredas.

La entrada llega acotada a 2000 caracteres (Tarea 11.1), lo que limita el costo
de las expresiones regulares.
"""

from __future__ import annotations

import re
from collections import Counter

from app.chat.dto import TextoRedactado
from app.chat.errors import RedaccionPiiError

PLACEHOLDER_CORREO = "[CORREO]"
PLACEHOLDER_DIRECCION = "[DIRECCION]"
PLACEHOLDER_UBICACION = "[UBICACION]"
PLACEHOLDER_NOMBRE = "[NOMBRE]"
PLACEHOLDER_TELEFONO = "[TELEFONO]"
PLACEHOLDER_NUMERO = "[NUMERO]"

# Una secuencia con al menos estos dígitos se trata como identificador personal.
MIN_DIGITOS_IDENTIFICADOR = 6

# Celular colombiano: 10 dígitos que empiezan por 3 (opcionalmente con indicativo 57).
_LONGITUD_CELULAR = 10
_INDICATIVO_COLOMBIA = "57"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DIRECCION = re.compile(
    r"\b(?:calle|cll?|carrera|cra|kra?|avenida|av|diagonal|dg|transversal|tv)\.?\s*"
    r"\d+\s*[a-z]?(?:\s*bis)?\s*(?:#|no\.?|n°|nro\.?|n[uú]mero)\s*"
    r"\d+\s*[a-z]?\s*-\s*\d+",
    re.IGNORECASE,
)
_COORDENADAS = re.compile(r"-?\d{1,3}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}")
_SECUENCIA_DIGITOS = re.compile(r"\+?\d(?:[\s.\-]?\d)+")
_MONEDA_DESPUES = re.compile(r"\s*(?:pesos|cop|mil|millones)\b", re.IGNORECASE)

# Palabras que cortan la captura del nombre ("me llamo Ana y tengo..." -> "Ana").
_CORTE_NOMBRE = r"(?:y|e|es|pero|tengo|soy|vivo|con|que|en|del|para|cultivo|siembro|trabajo)\b"
_PALABRA_NOMBRE = rf"(?!{_CORTE_NOMBRE})[^\W\d_]+"
_NOMBRE = re.compile(
    rf"(?P<pre>\b(?:me llamo|mi nombre es|mi nombre)\s*:?\s+)"
    rf"(?P<nombre>{_PALABRA_NOMBRE}(?:\s+{_PALABRA_NOMBRE}){{0,3}})",
    re.IGNORECASE,
)


def redactar_pii(texto: str) -> TextoRedactado:
    """Redacta la PII detectada en un texto antes de enviarlo al modelo (Req 3.10).

    Args:
        texto: mensaje del Usuario o transcripción STT, ya validado (Tarea 11.1).

    Returns:
        El texto con marcadores en lugar de la PII y el conteo por categoría.

    Raises:
        RedaccionPiiError: si la entrada no es texto o si tras redactar aún queda
            PII detectable; en ese caso no se debe invocar el modelo (Req 3.11).
    """
    if not isinstance(texto, str):
        raise RedaccionPiiError(internal_detail="chat_pii_input_not_text")
    conteo: Counter[str] = Counter()
    redactado = _aplicar_detectores(texto, conteo)
    if contiene_pii(redactado):
        raise RedaccionPiiError(internal_detail="chat_pii_residual_after_redaction")
    return TextoRedactado(texto=redactado, categorias=dict(conteo))


def contiene_pii(texto: str) -> bool:
    """Indica si el texto aún contiene PII detectable por los patrones del módulo.

    Args:
        texto: texto a inspeccionar.

    Returns:
        True si algún detector encuentra PII; False en caso contrario.
    """
    if any(patron.search(texto) for patron in (_EMAIL, _DIRECCION, _COORDENADAS, _NOMBRE)):
        return True
    return any(_es_identificador(m, texto) for m in _SECUENCIA_DIGITOS.finditer(texto))


def _aplicar_detectores(texto: str, conteo: Counter[str]) -> str:
    """Aplica los detectores en orden, de lo más específico a lo más general.

    Args:
        texto: texto original.
        conteo: acumulador de sustituciones por categoría (se modifica).

    Returns:
        El texto con todas las sustituciones aplicadas.
    """
    resultado = _sustituir(_EMAIL, PLACEHOLDER_CORREO, "correo", texto, conteo)
    resultado = _sustituir(_DIRECCION, PLACEHOLDER_DIRECCION, "direccion", resultado, conteo)
    resultado = _sustituir(_COORDENADAS, PLACEHOLDER_UBICACION, "ubicacion", resultado, conteo)
    resultado = _NOMBRE.sub(lambda m: _reemplazar_nombre(m, conteo), resultado)
    base = resultado
    return _SECUENCIA_DIGITOS.sub(lambda m: _reemplazar_secuencia(m, base, conteo), base)


def _sustituir(
    patron: re.Pattern[str], marcador: str, categoria: str, texto: str, conteo: Counter[str]
) -> str:
    """Reemplaza todas las coincidencias de un patrón y suma el conteo.

    Args:
        patron: expresión regular del detector.
        marcador: texto neutro que reemplaza a la PII.
        categoria: nombre de la categoría para el conteo.
        texto: texto de entrada.
        conteo: acumulador de sustituciones (se modifica).

    Returns:
        El texto con las coincidencias reemplazadas.
    """
    nuevo, cantidad = patron.subn(marcador, texto)
    if cantidad:
        conteo[categoria] += cantidad
    return nuevo


def _reemplazar_nombre(coincidencia: re.Match[str], conteo: Counter[str]) -> str:
    """Conserva la frase introductoria y reemplaza solo el nombre.

    Args:
        coincidencia: coincidencia de `_NOMBRE`.
        conteo: acumulador de sustituciones (se modifica).

    Returns:
        La frase introductoria seguida del marcador de nombre.
    """
    conteo["nombre"] += 1
    return coincidencia.group("pre") + PLACEHOLDER_NOMBRE


def _reemplazar_secuencia(
    coincidencia: re.Match[str], texto: str, conteo: Counter[str]
) -> str:
    """Reemplaza una secuencia de dígitos si es un identificador personal.

    Args:
        coincidencia: coincidencia de `_SECUENCIA_DIGITOS` sobre `texto`.
        texto: texto sobre el que se hizo la búsqueda (para revisar el contexto).
        conteo: acumulador de sustituciones (se modifica).

    Returns:
        El marcador de teléfono o número, o la secuencia original si es un monto
        o tiene menos de 6 dígitos.
    """
    if not _es_identificador(coincidencia, texto):
        return coincidencia.group()
    if _es_celular_colombiano(_solo_digitos(coincidencia.group())):
        conteo["telefono"] += 1
        return PLACEHOLDER_TELEFONO
    conteo["numero"] += 1
    return PLACEHOLDER_NUMERO


def _es_identificador(coincidencia: re.Match[str], texto: str) -> bool:
    """Indica si una secuencia de dígitos debe redactarse.

    Args:
        coincidencia: coincidencia de `_SECUENCIA_DIGITOS` sobre `texto`.
        texto: texto completo donde ocurrió la coincidencia.

    Returns:
        True si tiene 6 o más dígitos y no es un monto de dinero.
    """
    digitos = _solo_digitos(coincidencia.group())
    return len(digitos) >= MIN_DIGITOS_IDENTIFICADOR and not _es_monto(coincidencia, texto)


def _es_monto(coincidencia: re.Match[str], texto: str) -> bool:
    """Indica si la secuencia es un monto: precedida de "$" o seguida de una moneda.

    Args:
        coincidencia: coincidencia de `_SECUENCIA_DIGITOS` sobre `texto`.
        texto: texto completo donde ocurrió la coincidencia.

    Returns:
        True si el contexto indica que es un valor en dinero.
    """
    precedido_de_signo = texto[: coincidencia.start()].rstrip().endswith("$")
    seguido_de_moneda = _MONEDA_DESPUES.match(texto, coincidencia.end()) is not None
    return precedido_de_signo or seguido_de_moneda


def _es_celular_colombiano(digitos: str) -> bool:
    """Indica si los dígitos corresponden a un celular colombiano.

    Args:
        digitos: solo los dígitos de la secuencia.

    Returns:
        True si son 10 dígitos que empiezan por 3, con o sin indicativo 57.
    """
    if len(digitos) == _LONGITUD_CELULAR + len(_INDICATIVO_COLOMBIA) and digitos.startswith(
        _INDICATIVO_COLOMBIA
    ):
        digitos = digitos[len(_INDICATIVO_COLOMBIA):]
    return len(digitos) == _LONGITUD_CELULAR and digitos.startswith("3")


def _solo_digitos(valor: str) -> str:
    """Devuelve únicamente los dígitos de una cadena.

    Args:
        valor: cadena con dígitos y separadores.

    Returns:
        La cadena sin caracteres que no sean dígitos.
    """
    return re.sub(r"\D", "", valor)
