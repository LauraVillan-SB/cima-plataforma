"""Pruebas del servicio de hashing de la Clave.

Feature: cima-plataforma, Property 2: Round-trip de hashing de la Clave.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.password import hash_clave, verify_clave

# Estrategia: claves válidas de exactamente 4 dígitos ("0000".."9999").
_claves_validas = st.integers(min_value=0, max_value=9999).map(lambda n: f"{n:04d}")


# Feature: cima-plataforma, Property 2: Round-trip de hashing de la Clave.
# Validates: Requirements 1.5
# bcrypt es costoso; se acota a 100 iteraciones (mínimo exigido) con deadline amplio.
@settings(max_examples=100, deadline=None)
@given(clave=_claves_validas, otra=_claves_validas)
def test_property_2_round_trip_de_hashing(clave: str, otra: str) -> None:
    """El hash difiere del texto plano; verify acierta con la Clave y falla con otra."""
    # Given una Clave válida
    # When se calcula su hash
    hashed = hash_clave(clave)

    # Then el hash nunca coincide con el texto plano (Req 1.5)
    assert hashed != clave
    # And verify(clave, hash) es verdadero
    assert verify_clave(clave, hashed) is True
    # And verify(otra_clave, hash) es falso cuando la otra Clave es distinta
    if otra != clave:
        assert verify_clave(otra, hashed) is False


@settings(max_examples=25, deadline=None)
@given(clave=_claves_validas)
def test_hashing_usa_sal_distinta_por_llamada(clave: str) -> None:
    """Dos hashes de la misma Clave difieren (sal aleatoria), pero ambos verifican."""
    # Given la misma Clave hasheada dos veces
    h1 = hash_clave(clave)
    h2 = hash_clave(clave)
    # Then los hashes difieren por la sal, y ambos verifican correctamente
    assert h1 != h2
    assert verify_clave(clave, h1) is True
    assert verify_clave(clave, h2) is True
