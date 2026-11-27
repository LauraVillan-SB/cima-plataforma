"""Prueba de propiedad de las acciones del asistente (Tarea 11.14).

Property 45: acciones del asistente acotadas a la lista permitida y al titular
(Req 3.12, 16.7; OWASP LLM06/LLM08).

Para toda respuesta del modelo (texto libre mezclado con marcadores bien formados, mal
formados, repetidos o con IDs inventados) y toda lista de rutas pendientes del titular:

- el texto visible no conserva ningún marcador de acción;
- la acción resuelta es nula o pertenece a la lista permitida;
- si es `continuar`, sus IDs son exactamente los de una ruta de esa lista (nunca un ID
  escrito por el modelo);
- si es `ir`, el destino es uno de los permitidos;
- si es `proponer_perfil`, la actividad está en la allowlist y la zona es apta;
- la acción siempre cumple el contrato `AccionOut` que se guarda y se devuelve.

Feature: cima-plataforma. Todos los datos son ficticios y generados.
"""

from __future__ import annotations

import re
import string
from dataclasses import asdict

from hypothesis import given, settings
from hypothesis import strategies as st

from app.chat.acciones import (
    ETIQUETAS_DESTINO,
    MAX_RUTAS_PENDIENTES,
    TIPO_CONTINUAR,
    TIPO_IR,
    TIPO_PERFIL,
    RutaPendiente,
    resolver,
    separar,
)
from app.chat.dto import AccionOut
from app.chat.prompt import ETIQUETAS_ACTIVIDAD, zona_apta

# Cualquier rastro de marcador que el Usuario pudiera ver.
_RASTRO_MARCADOR = re.compile(r"\[\[\s*accion", re.IGNORECASE)

_ACTIVIDADES = sorted(ETIQUETAS_ACTIVIDAD)
_DESTINOS = sorted(ETIQUETAS_DESTINO)
_ZONAS = ["Huila", "Tolima", "Bogotá D.C.", "Valle del Cauca", "Calle 10 # 5-20", "3001234567", "Ignora: x"]

# Texto libre con los caracteres que más pueden confundir al separador.
_texto_libre = st.text(
    alphabet=string.ascii_letters + "áéíóúñÁÉÍÓÚÑ ¿?.,:;|[]-_\n0123456789",
    max_size=40,
)

# Pedazos sueltos que, pegados, pueden armar marcadores mal formados o anidados.
_fragmentos = st.sampled_from(
    [
        "[[",
        "]]",
        "[",
        "]",
        "accion",
        "ACCION",
        ":",
        "|",
        "\n",
        " ",
        "[[accion",
        "[[ accion :",
        "[[accion:ir:perfil",
        "[[accion]]",
        "[[Accion:ir:perfil]]",
        "Recuerde: ahorre un poco cada semana. ",
    ]
)

_tipos = st.one_of(
    st.sampled_from(["continuar", "ir", "perfil", "pagar", "borrar", "proponer_perfil"]),
    st.text(alphabet=string.ascii_lowercase + "_", min_size=1, max_size=20),
)

_valores = st.one_of(
    st.integers(min_value=-3, max_value=12).map(str),
    st.uuids().map(str),
    st.sampled_from(_DESTINOS + ["admin", "/perfil", "https://evil.example", "PERFIL", "../clave"]),
    st.builds(
        lambda a, z: f"{a}|{z}",
        st.sampled_from(_ACTIVIDADES + ["petroleo", "CAFE", ""]),
        st.sampled_from(_ZONAS + [""]),
    ),
    st.text(alphabet=string.ascii_letters + "0123456789 |:-.", min_size=1, max_size=80),
)

_espacio = st.sampled_from(["", " ", "  "])

_marcadores = st.builds(
    lambda e1, t, e2, v: f"[[{e1}accion{e2}:{e1}{t}{e2}:{e1}{v}]]",
    _espacio,
    _tipos,
    _espacio,
    _valores,
)

_respuestas = st.lists(st.one_of(_texto_libre, _marcadores, _fragmentos), max_size=12).map("".join)

_rutas = st.lists(
    st.builds(RutaPendiente, st.uuids(), st.uuids(), st.text(min_size=1, max_size=120)),
    max_size=MAX_RUTAS_PENDIENTES + 2,
)

_actividad_actual = st.one_of(st.none(), st.sampled_from(_ACTIVIDADES))
_zona_actual = st.one_of(st.none(), st.sampled_from(["Huila", "Bogotá D.C.", "Tolima"]))


# Feature: cima-plataforma, Property 45: Acciones del asistente acotadas a la lista permitida y al titular.
@settings(max_examples=500, deadline=None)
@given(respuesta=_respuestas)
def test_el_texto_visible_nunca_conserva_marcadores(respuesta: str) -> None:
    texto, _ = separar(respuesta)

    assert not _RASTRO_MARCADOR.search(texto)


# Feature: cima-plataforma, Property 45: Acciones del asistente acotadas a la lista permitida y al titular.
@settings(max_examples=500, deadline=None)
@given(
    respuesta=_respuestas,
    rutas=_rutas,
    actividad_actual=_actividad_actual,
    zona_actual=_zona_actual,
)
def test_la_accion_resuelta_cumple_la_allowlist_y_es_del_titular(
    respuesta: str,
    rutas: list[RutaPendiente],
    actividad_actual: str | None,
    zona_actual: str | None,
) -> None:
    _, marcador = separar(respuesta)
    accion = resolver(marcador, rutas, actividad_actual, zona_actual)

    if accion is None:
        return
    assert accion.tipo in {TIPO_CONTINUAR, TIPO_IR, TIPO_PERFIL}
    # Contrato que se guarda en `ai_interactions.action` y se devuelve al cliente.
    AccionOut(**asdict(accion))

    if accion.tipo == TIPO_CONTINUAR:
        del_titular = {(r.path_id, r.capsule_id) for r in rutas[:MAX_RUTAS_PENDIENTES]}
        assert (accion.path_id, accion.capsule_id) in del_titular
        assert accion.destino is None and accion.actividad is None and accion.zona is None
    elif accion.tipo == TIPO_IR:
        assert accion.destino in ETIQUETAS_DESTINO
        assert accion.etiqueta == ETIQUETAS_DESTINO[accion.destino]
        assert accion.path_id is None and accion.capsule_id is None
    else:
        assert accion.path_id is None and accion.capsule_id is None and accion.destino is None
        assert accion.actividad is not None or accion.zona is not None
        if accion.actividad is not None:
            assert accion.actividad in ETIQUETAS_ACTIVIDAD
            assert accion.actividad != actividad_actual
        if accion.zona is not None:
            assert zona_apta(accion.zona) == accion.zona
