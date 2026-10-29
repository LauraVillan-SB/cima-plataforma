"""Pruebas de validación de la Clave y del DTO de registro.

Feature: cima-plataforma, Property 1: Validación de la Clave de 4 dígitos.
"""
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.auth.dto import IngresoRequest, RegistroRequest

_CLAVE_VALIDA = re.compile(r"^\d{4}$")
_TELEFONO_VALIDO = "3001234567"


# Feature: cima-plataforma, Property 1: Validación de la Clave de 4 dígitos.
# Validates: Requirements 1.4
@given(entrada=st.text(max_size=12))
def test_property_1_clave_aceptada_sii_cuatro_digitos(entrada: str) -> None:
    """La Clave se acepta si y solo si es exactamente 4 dígitos numéricos."""
    # Given una entrada arbitraria y un teléfono válido
    es_clave_valida = bool(_CLAVE_VALIDA.fullmatch(entrada))

    # When se intenta construir el DTO de ingreso con esa entrada como Clave
    def construir() -> IngresoRequest:
        return IngresoRequest(telefono=_TELEFONO_VALIDO, clave=entrada)

    # Then se acepta solo si la entrada son 4 dígitos; de lo contrario se rechaza
    if es_clave_valida:
        assert construir().clave == entrada
    else:
        with pytest.raises(ValidationError):
            construir()


@given(digitos=st.integers(min_value=0, max_value=9999))
def test_property_1_toda_clave_de_cuatro_digitos_es_valida(digitos: int) -> None:
    """Toda cadena de exactamente 4 dígitos (incluyendo ceros a la izquierda) es válida."""
    # Given una clave de 4 dígitos con posibles ceros a la izquierda
    clave = f"{digitos:04d}"
    # When / Then el DTO la acepta
    assert IngresoRequest(telefono=_TELEFONO_VALIDO, clave=clave).clave == clave


def test_registro_rechaza_claves_que_no_coinciden() -> None:
    """La doble confirmación de Clave debe coincidir exactamente (Req 1.3)."""
    # Given una Clave y una confirmación distintas
    # When se construye el DTO de registro
    # Then se rechaza con error de validación
    with pytest.raises(ValidationError):
        RegistroRequest(
            telefono=_TELEFONO_VALIDO, clave="1234", confirmacion_clave="4321"
        )


def test_registro_acepta_claves_que_coinciden() -> None:
    """El registro se acepta cuando Clave y confirmación coinciden."""
    # Given una Clave y confirmación idénticas
    # When se construye el DTO
    dto = RegistroRequest(
        telefono=_TELEFONO_VALIDO, clave="1234", confirmacion_clave="1234"
    )
    # Then el DTO es válido
    assert dto.clave == "1234"


def test_registro_rechaza_campos_no_permitidos() -> None:
    """La allowlist (extra='forbid') rechaza claves no permitidas (Zero Trust)."""
    # Given una solicitud con un campo extra (p. ej. intento de inyectar 'cedula')
    # When se construye el DTO
    # Then se rechaza
    with pytest.raises(ValidationError):
        RegistroRequest(
            telefono=_TELEFONO_VALIDO,
            clave="1234",
            confirmacion_clave="1234",
            cedula="1234567890",
        )


@pytest.mark.parametrize("telefono", ["123456", "1234567890123456", "abc1234", ""])
def test_ingreso_rechaza_telefono_invalido(telefono: str) -> None:
    """El teléfono debe tener 7-15 dígitos numéricos (Req 1.1 / 9.2)."""
    with pytest.raises(ValidationError):
        IngresoRequest(telefono=telefono, clave="1234")
