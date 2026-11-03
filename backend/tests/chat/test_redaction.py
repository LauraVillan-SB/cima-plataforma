"""Pruebas de la redacción de PII previa al modelo de IA (Tarea 11.2).

Cubren la sustitución de cada tipo de PII por un marcador (Req 3.10, 14.6), la
conservación del texto sin PII y de los montos de dinero, y el rechazo cuando
la redacción no puede completarse (Req 3.11). Funciones puras: sin BD ni
servicios externos. Todos los datos personales son ficticios.
"""
from __future__ import annotations

import pytest

from app.chat import redaction
from app.chat.errors import RedaccionPiiError
from app.chat.redaction import (
    PLACEHOLDER_CORREO,
    PLACEHOLDER_DIRECCION,
    PLACEHOLDER_NOMBRE,
    PLACEHOLDER_NUMERO,
    PLACEHOLDER_TELEFONO,
    PLACEHOLDER_UBICACION,
    contiene_pii,
    redactar_pii,
)

# --- Sustitución por tipo de PII (Req 3.10) ---------------------------------


@pytest.mark.parametrize(
    "texto",
    ["mi número es 300 123 4567", "escríbeme al +57 3001234567", "cel: 310-987-6543"],
)
def test_redacta_celular_colombiano(texto: str) -> None:
    """Los celulares, con o sin indicativo y separadores, se marcan como teléfono."""
    # Given un texto con un celular ficticio
    # When se redacta
    resultado = redactar_pii(texto)
    # Then el celular queda como [TELEFONO] y no queda ningún dígito del número
    assert PLACEHOLDER_TELEFONO in resultado.texto
    assert resultado.categorias == {"telefono": 1}
    assert not any(caracter.isdigit() for caracter in resultado.texto)


@pytest.mark.parametrize("texto", ["mi cédula es 1.023.456.789", "fijo 601 2345678"])
def test_redacta_otros_identificadores_numericos(texto: str) -> None:
    """Cédulas, fijos y otros números de 6 o más dígitos se marcan como número."""
    resultado = redactar_pii(texto)
    assert PLACEHOLDER_NUMERO in resultado.texto
    assert resultado.categorias == {"numero": 1}


def test_redacta_correo() -> None:
    """Un correo electrónico se reemplaza por [CORREO]."""
    resultado = redactar_pii("mi correo es ana.perez+cima@ejemplo.com")
    assert resultado.texto == f"mi correo es {PLACEHOLDER_CORREO}"
    assert resultado.categorias == {"correo": 1}


@pytest.mark.parametrize(
    "texto", ["vivo en la Calle 45 # 12-30", "queda en Cra 7 No 32-16", "Av. 68 #12A-30"]
)
def test_redacta_direccion_colombiana(texto: str) -> None:
    """Las direcciones con nomenclatura colombiana se reemplazan por [DIRECCION]."""
    resultado = redactar_pii(texto)
    assert PLACEHOLDER_DIRECCION in resultado.texto
    assert resultado.categorias == {"direccion": 1}


def test_redacta_coordenadas() -> None:
    """Un par de coordenadas se reemplaza por [UBICACION]."""
    resultado = redactar_pii("la finca está en 4.6097, -74.0817")
    assert resultado.texto == f"la finca está en {PLACEHOLDER_UBICACION}"


def test_redacta_nombre_y_conserva_el_resto_de_la_frase() -> None:
    """Se reemplaza solo el nombre y se conserva el contexto útil para el modelo."""
    # Given una presentación con nombre y una pregunta
    texto = "me llamo María Pérez y tengo una tienda"
    # When se redacta
    resultado = redactar_pii(texto)
    # Then el nombre se marca y el resto de la frase sigue igual
    assert resultado.texto == f"me llamo {PLACEHOLDER_NOMBRE} y tengo una tienda"
    assert resultado.categorias == {"nombre": 1}


def test_redacta_nombre_en_minusculas() -> None:
    """Usuarios con baja alfabetización digital pueden escribir sin mayúsculas."""
    resultado = redactar_pii("mi nombre es juan carlos rodríguez gómez")
    assert resultado.texto == f"mi nombre es {PLACEHOLDER_NOMBRE}"


def test_cuenta_cada_sustitucion_por_categoria() -> None:
    """El conteo refleja cuántas PII se redactaron, sin guardar los valores."""
    resultado = redactar_pii("llámame al 3001234567 o al 3109876543, o a ana@ejemplo.com")
    assert resultado.categorias == {"correo": 1, "telefono": 2}
    assert "3001234567" not in str(resultado.categorias)


# --- Contenido que se conserva -----------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "¿cómo protejo mi cultivo de papa de la sequía?",
        "tengo 20 vacas y 3 hectáreas de café",
        "hola, me llamo y tengo dudas",
    ],
)
def test_conserva_texto_sin_pii(texto: str) -> None:
    """Un texto sin PII llega al modelo tal cual y sin categorías."""
    resultado = redactar_pii(texto)
    assert resultado.texto == texto
    assert resultado.categorias == {}


@pytest.mark.parametrize(
    "texto",
    [
        "me prestaron $1.500.000 para abono",
        "me prestaron $ 1.500.000 para abono",
        "debo 1.500.000 pesos al banco",
        "gano 2.000.000 mil al mes",
    ],
)
def test_conserva_montos_de_dinero(texto: str) -> None:
    """Los montos son necesarios para la educación financiera y no son PII."""
    assert redactar_pii(texto).texto == texto


# --- Verificación y fallo de la redacción (Req 3.11) -------------------------


def test_el_resultado_no_contiene_pii_detectable() -> None:
    """Tras redactar, ningún detector encuentra PII en el texto (Property 9)."""
    texto = (
        "me llamo Ana Gómez, mi cédula es 1023456789, vivo en Calle 10 # 5-20, "
        "mi correo es ana@ejemplo.com y mi celular es 3001234567"
    )
    resultado = redactar_pii(texto)
    assert contiene_pii(texto)
    assert not contiene_pii(resultado.texto)


def test_falla_si_queda_pii_tras_redactar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si la redacción no se completa, se lanza error y no hay texto para el modelo."""
    # Given una redacción que no logra quitar la PII (simula un fallo interno)
    monkeypatch.setattr(redaction, "_aplicar_detectores", lambda texto, conteo: texto)
    # When se redacta un texto con un celular / Then se rechaza (Req 3.11)
    with pytest.raises(RedaccionPiiError):
        redactar_pii("mi celular es 3001234567")


def test_falla_si_la_entrada_no_es_texto() -> None:
    """Una entrada que no es texto no puede redactarse con seguridad."""
    with pytest.raises(RedaccionPiiError):
        redactar_pii(3001234567)  # type: ignore[arg-type]


def test_error_pide_reformular_sin_exponer_el_contenido(monkeypatch: pytest.MonkeyPatch) -> None:
    """El mensaje público pide reformular sin datos personales y no incluye la PII."""
    monkeypatch.setattr(redaction, "_aplicar_detectores", lambda texto, conteo: texto)
    with pytest.raises(RedaccionPiiError) as error:
        redactar_pii("mi celular es 3001234567")
    assert "datos personales" in error.value.public_message
    assert "3001234567" not in error.value.public_message
    assert "3001234567" not in error.value.internal_detail
