"""Acciones que el asistente puede proponer dentro de la app (OWASP LLM06/LLM08).

El modelo solo PROPONE: agrega al final de su respuesta un marcador como
`[[accion:continuar:1]]`, `[[accion:ir:perfil]]` o `[[accion:perfil:cafe|Huila]]`.
El servidor:

1. Quita todos los marcadores del texto visible (`separar`).
2. Resuelve el primero contra una allowlist y contra los datos del propio Usuario,
   leídos en el servidor (`resolver`). El modelo nunca entrega IDs: `continuar:N`
   es la posición N de la lista numerada que el servidor le pasó en el contexto, y
   el ID de la ruta y de la cápsula se toma de esa lista (anti-BOLA, Req 6.7).
3. Arma la etiqueta del botón con textos fijos del servidor, no con texto del modelo.

Nada se ejecuta aquí. El cliente muestra un botón; navegar es inocuo y cambiar el
Perfil pide confirmación y pasa por `PUT /api/v1/perfiles/{id}`, que vuelve a
validar todo (Req 9.1, 9.2). El asistente nunca pide ni recibe la Clave: para
cambiarla solo lleva a la pantalla de cambio de Clave (Req 1).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from app.chat.prompt import ETIQUETAS_ACTIVIDAD, zona_apta

TIPO_CONTINUAR = "continuar"
TIPO_IR = "ir"
TIPO_PERFIL = "proponer_perfil"

TipoAccion = Literal["continuar", "ir", "proponer_perfil"]

# Destinos permitidos para `ir` (allowlist). La ruta del cliente la fija el
# frontend a partir de esta clave; el modelo no escribe rutas.
ETIQUETAS_DESTINO: dict[str, str] = {
    "mi_ruta": "Ver mis rutas",
    "perfil": "Ir a mi perfil",
    "cambiar_clave": "Cambiar mi clave",
    "descargas": "Ver mis descargas",
}

# Máximo de rutas pendientes que se numeran en el contexto del modelo.
MAX_RUTAS_PENDIENTES = 5

# Marcador bien formado. El cuerpo es corto y sin saltos de línea ni corchetes.
_MARCADOR = re.compile(r"\[\[\s*accion\s*:\s*([a-z_]{1,20})\s*:\s*([^\[\]\n]{1,80})\]\]")
# Cualquier resto con forma de marcador (incluso mal formado) se quita del texto
# visible para que el Usuario nunca vea instrucciones internas.
_RESTO_MARCADOR = re.compile(r"\[\[\s*accion[^\]\n]{0,120}\]?\]?", re.IGNORECASE)


@dataclass(frozen=True)
class RutaPendiente:
    """Ruta sin terminar del Usuario, leída en el servidor con su avance real."""

    path_id: uuid.UUID
    capsule_id: uuid.UUID
    titulo: str


@dataclass(frozen=True)
class AccionAgente:
    """Acción ya resuelta por el servidor, lista para mostrarse como botón."""

    tipo: TipoAccion
    etiqueta: str
    destino: str | None = None
    path_id: uuid.UUID | None = None
    capsule_id: uuid.UUID | None = None
    actividad: str | None = None
    zona: str | None = None


@dataclass(frozen=True)
class Marcador:
    """Marcador crudo propuesto por el modelo (todavía no confiable)."""

    tipo: str
    valor: str


def separar(texto: str) -> tuple[str, Marcador | None]:
    """Quita los marcadores del texto y devuelve el primero bien formado.

    Args:
        texto: respuesta del modelo.

    Returns:
        El texto sin marcadores (espacios normalizados al final) y el primer
        marcador, o `None` si no había uno bien formado.
    """
    encontrado = _MARCADOR.search(texto)
    marcador = Marcador(encontrado.group(1), encontrado.group(2).strip()) if encontrado else None
    limpio = _RESTO_MARCADOR.sub("", _MARCADOR.sub("", texto))
    return limpio.strip(), marcador


def resolver(
    marcador: Marcador | None,
    rutas: list[RutaPendiente],
    actividad_actual: str | None,
    zona_actual: str | None,
) -> AccionAgente | None:
    """Convierte un marcador en una acción permitida, o la descarta.

    Args:
        marcador: lo que propuso el modelo.
        rutas: rutas pendientes del Usuario, en el mismo orden numerado que se
            le pasó al modelo.
        actividad_actual: actividad del Perfil, para no proponer lo mismo.
        zona_actual: zona del Perfil, para no proponer lo mismo.

    Returns:
        La acción resuelta, o `None` si el marcador no cumple la allowlist.
    """
    if marcador is None:
        return None
    if marcador.tipo == TIPO_CONTINUAR:
        return _resolver_continuar(marcador.valor, rutas)
    if marcador.tipo == TIPO_IR:
        return _resolver_ir(marcador.valor)
    if marcador.tipo == "perfil":
        return _resolver_perfil(marcador.valor, actividad_actual, zona_actual)
    return None


def _resolver_continuar(valor: str, rutas: list[RutaPendiente]) -> AccionAgente | None:
    """`continuar:N` con N entre 1 y la cantidad de rutas listadas."""
    if not valor.isdigit() or len(valor) > 2:
        return None
    indice = int(valor)
    if not 1 <= indice <= min(len(rutas), MAX_RUTAS_PENDIENTES):
        return None
    ruta = rutas[indice - 1]
    return AccionAgente(
        tipo=TIPO_CONTINUAR,
        etiqueta=f"Continuar: {ruta.titulo}",
        path_id=ruta.path_id,
        capsule_id=ruta.capsule_id,
    )


def _resolver_ir(valor: str) -> AccionAgente | None:
    """`ir:DESTINO` solo con destinos de la allowlist."""
    etiqueta = ETIQUETAS_DESTINO.get(valor)
    if etiqueta is None:
        return None
    return AccionAgente(tipo=TIPO_IR, etiqueta=etiqueta, destino=valor)


def _resolver_perfil(
    valor: str, actividad_actual: str | None, zona_actual: str | None
) -> AccionAgente | None:
    """`perfil:ACTIVIDAD|ZONA`; cualquiera de los dos puede ir vacío, no ambos.

    La actividad debe estar en la allowlist del Perfil y la zona pasar `zona_apta`
    (sin dígitos ni PII). Lo que no cambia frente al Perfil actual se omite.
    """
    actividad_txt, _, zona_txt = valor.partition("|")
    actividad_txt = actividad_txt.strip().lower()
    zona_txt = zona_txt.strip()

    actividad: str | None = None
    if actividad_txt:
        if actividad_txt not in ETIQUETAS_ACTIVIDAD:
            return None
        actividad = actividad_txt if actividad_txt != actividad_actual else None

    zona: str | None = None
    if zona_txt:
        zona = zona_apta(zona_txt)
        if zona is None:
            return None
        if zona_actual and zona.casefold() == zona_actual.strip().casefold():
            zona = None

    if actividad is None and zona is None:
        return None
    partes = []
    if actividad:
        partes.append(f"actividad: {ETIQUETAS_ACTIVIDAD[actividad]}")
    if zona:
        partes.append(f"zona: {zona}")
    return AccionAgente(
        tipo=TIPO_PERFIL,
        etiqueta="Actualizar mi perfil (" + ", ".join(partes) + ")",
        actividad=actividad,
        zona=zona,
    )


def contexto_de_rutas(rutas: list[RutaPendiente]) -> str:
    """Lista numerada de rutas pendientes para el modelo, sin IDs ni PII.

    Los títulos son del catálogo del servidor; igual se limpian de saltos de
    línea y se acortan para que no parezcan instrucciones.
    """
    if not rutas:
        return "Rutas pendientes: ninguna."
    lineas = [
        f"{i}. {' '.join(r.titulo.split())[:80]}"
        for i, r in enumerate(rutas[:MAX_RUTAS_PENDIENTES], start=1)
    ]
    return "Rutas pendientes: " + " ".join(lineas)
