"""Servicio de hashing de la Clave (Req 1.5).

Usa passlib con bcrypt (hash con sal). La Clave nunca se almacena ni registra en
texto plano. Expone funciones puras para hashear y verificar, aislando el
algoritmo tras una interfaz estable (permite migrar a argon2 sin cambiar llamadas).
"""
from passlib.context import CryptContext

# Contexto de hashing: bcrypt como esquema activo. `deprecated="auto"` permite
# re-hashear de forma transparente si en el futuro se cambia de algoritmo.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_clave(clave: str) -> str:
    """Devuelve el hash con sal de la Clave.

    :param clave: Clave en texto plano (previamente validada como 4 dígitos).
    :return: hash bcrypt con sal; nunca coincide con el texto plano (Req 1.5).
    """
    return _pwd_context.hash(clave)


def verify_clave(clave: str, clave_hash: str) -> bool:
    """Verifica una Clave contra su hash almacenado.

    :param clave: Clave en texto plano a verificar.
    :param clave_hash: hash previamente generado por :func:`hash_clave`.
    :return: ``True`` si la Clave corresponde al hash, ``False`` en caso contrario.
    """
    return _pwd_context.verify(clave, clave_hash)
