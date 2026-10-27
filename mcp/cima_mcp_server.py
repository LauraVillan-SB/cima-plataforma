#!/usr/bin/env python3
"""Servidor MCP propio del proyecto CIMA.

Expone herramientas de dominio de la plataforma educativa CIMA (Seguros Bolivar),
alineadas con los requisitos del spec en `.kiro/specs/cima-plataforma/`:

- validate_user_profile : valida un Perfil de Usuario segun Requirement 9.
- validate_clave        : valida la Clave de 4 digitos segun Requirement 1.
- mask_pii              : enmascara PII dejando a lo sumo los ultimos 4 caracteres
                          (Requirement 5.9 / 9.4).
- list_requirements     : lista los requisitos del spec para trazabilidad.

Implementa el protocolo MCP (JSON-RPC 2.0 por stdio) usando SOLO la libreria
estandar de Python, por lo que no requiere instalar dependencias ni `uv`.
No accede a red ni a secretos: toda la logica es local y deterministica.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "cima-project"
SERVER_VERSION = "1.0.0"

# Raiz del proyecto: este archivo vive en <root>/mcp/cima_mcp_server.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = (
    PROJECT_ROOT / ".kiro" / "specs" / "cima-plataforma" / "requirements.md"
)

# Lista de valores permitidos para tipo de cultivo o comercio (allowlist, Req 9.2).
# Allowlist sobre blocklist: cualquier valor fuera de esta lista se rechaza.
ALLOWED_ACTIVITY_TYPES: frozenset[str] = frozenset(
    {
        "cafe",
        "platano",
        "aguacate",
        "cacao",
        "arroz",
        "maiz",
        "ganaderia",
        "hortalizas",
        "tienda_barrio",
        "panaderia",
        "miscelanea",
        "fruteria",
    }
)

# E.164 relajado para Colombia: entre 7 y 15 digitos, opcional prefijo '+'.
PHONE_PATTERN = re.compile(r"^\+?\d{7,15}$")
CLAVE_PATTERN = re.compile(r"^\d{4}$")


# --------------------------------------------------------------------------- #
# Logica de dominio (pura, testeable, sin efectos secundarios)
# --------------------------------------------------------------------------- #
def _normalize(value: str) -> str:
    """Normaliza una entrada de texto eliminando espacios (trim). Req 9.2."""
    return value.strip()


def validate_user_profile(
    phone: str, activity_type: str, geo_zone: str
) -> dict[str, Any]:
    """Valida un Perfil de Usuario segun Requirement 9.

    Reglas: solo campos permitidos, telefono 7-15 digitos, tipo de actividad en
    allowlist, zona geografica <= 100 caracteres. Devuelve el detalle de errores
    por campo en lugar de un mensaje generico, para uso en desarrollo.
    """
    errors: list[str] = []

    phone_n = _normalize(phone)
    if not PHONE_PATTERN.match(phone_n):
        errors.append("phone: debe tener entre 7 y 15 digitos numericos (E.164)")

    activity_n = _normalize(activity_type).lower()
    if activity_n not in ALLOWED_ACTIVITY_TYPES:
        errors.append(
            "activity_type: valor no permitido; use uno de la lista aprobada"
        )

    geo_n = _normalize(geo_zone)
    if len(geo_n) == 0:
        errors.append("geo_zone: no puede estar vacia")
    elif len(geo_n) > 100:
        errors.append("geo_zone: excede 100 caracteres")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "normalized": {
            "phone": phone_n,
            "activity_type": activity_n,
            "geo_zone": geo_n,
        },
    }


def validate_clave(clave: str, confirmation: str | None = None) -> dict[str, Any]:
    """Valida la Clave de 4 digitos segun Requirement 1.

    La Clave debe ser exactamente 4 digitos numericos (Req 1.5). Si se envia
    `confirmation`, debe coincidir exactamente (Req 1.2 / 1.4). No se almacena ni
    se registra la Clave; esta funcion solo valida formato y coincidencia.
    """
    errors: list[str] = []

    if not CLAVE_PATTERN.match(clave or ""):
        errors.append("clave: debe ser exactamente 4 digitos numericos")

    if confirmation is not None and clave != confirmation:
        errors.append("confirmation: la confirmacion no coincide con la Clave")

    return {"valid": len(errors) == 0, "errors": errors}


def mask_pii(value: str, visible: int = 4) -> dict[str, Any]:
    """Enmascara PII dejando visibles a lo sumo los ultimos `visible` caracteres.

    Implementa la regla de Req 5.9 / 9.4. Ej: '3001234567' -> '******4567'.
    """
    safe_value = value or ""
    keep = max(0, min(visible, len(safe_value)))
    masked = "*" * (len(safe_value) - keep) + safe_value[len(safe_value) - keep :]
    return {"masked": masked, "visible_chars": keep}


def list_requirements() -> dict[str, Any]:
    """Lista los titulos de requisitos del spec para trazabilidad.

    Lee `.kiro/specs/cima-plataforma/requirements.md` (solo lectura, ruta fija
    dentro del proyecto). No acepta rutas del usuario, por lo que no hay riesgo
    de path traversal.
    """
    if not REQUIREMENTS_FILE.is_file():
        return {"found": False, "requirements": [], "source": str(REQUIREMENTS_FILE)}

    text = REQUIREMENTS_FILE.read_text(encoding="utf-8")
    titles = re.findall(r"^### (Requirement \d+:.*)$", text, flags=re.MULTILINE)
    return {
        "found": True,
        "count": len(titles),
        "requirements": titles,
        "source": str(REQUIREMENTS_FILE.relative_to(PROJECT_ROOT)),
    }


# --------------------------------------------------------------------------- #
# Definicion de herramientas MCP
# --------------------------------------------------------------------------- #
TOOLS: list[dict[str, Any]] = [
    {
        "name": "validate_user_profile",
        "description": (
            "Valida un Perfil de Usuario de CIMA segun el Requirement 9: campos "
            "permitidos, telefono de 7-15 digitos, tipo de cultivo/comercio en "
            "allowlist y zona geografica <= 100 caracteres."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Numero de telefono"},
                "activity_type": {
                    "type": "string",
                    "description": "Tipo de cultivo o comercio",
                },
                "geo_zone": {"type": "string", "description": "Zona geografica"},
            },
            "required": ["phone", "activity_type", "geo_zone"],
        },
    },
    {
        "name": "validate_clave",
        "description": (
            "Valida la Clave de 4 digitos de CIMA segun el Requirement 1 "
            "(formato de 4 digitos y, opcionalmente, coincidencia de confirmacion). "
            "No almacena ni registra la Clave."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "clave": {"type": "string", "description": "Clave de 4 digitos"},
                "confirmation": {
                    "type": "string",
                    "description": "Confirmacion de la Clave (opcional)",
                },
            },
            "required": ["clave"],
        },
    },
    {
        "name": "mask_pii",
        "description": (
            "Enmascara un valor de PII dejando visibles como maximo los ultimos N "
            "caracteres (Requirement 5.9 / 9.4). Por defecto deja 4 visibles."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "Valor a enmascarar"},
                "visible": {
                    "type": "integer",
                    "description": "Caracteres visibles al final (default 4)",
                    "default": 4,
                },
            },
            "required": ["value"],
        },
    },
    {
        "name": "list_requirements",
        "description": (
            "Lista los titulos de los requisitos del spec de CIMA para trazabilidad "
            "entre codigo y requisitos (solo lectura)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

TOOL_DISPATCH = {
    "validate_user_profile": lambda a: validate_user_profile(
        a.get("phone", ""), a.get("activity_type", ""), a.get("geo_zone", "")
    ),
    "validate_clave": lambda a: validate_clave(
        a.get("clave", ""), a.get("confirmation")
    ),
    "mask_pii": lambda a: mask_pii(a.get("value", ""), int(a.get("visible", 4))),
    "list_requirements": lambda a: list_requirements(),
}


# --------------------------------------------------------------------------- #
# Transporte JSON-RPC 2.0 por stdio
# --------------------------------------------------------------------------- #
def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    """Procesa un mensaje JSON-RPC y devuelve la respuesta (o None si es notificacion)."""
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "notifications/initialized":
        return None  # Notificacion: no requiere respuesta.

    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = TOOL_DISPATCH.get(tool_name)
        if handler is None:
            return _error(request_id, -32602, f"Herramienta desconocida: {tool_name}")
        try:
            output = handler(arguments)
        except (TypeError, ValueError) as exc:
            return _error(request_id, -32602, f"Argumentos invalidos: {exc}")
        return _result(
            request_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(output, ensure_ascii=False)}
                ]
            },
        )

    if request_id is None:
        return None  # Otras notificaciones no soportadas: se ignoran en silencio.

    return _error(request_id, -32601, f"Metodo no soportado: {method}")


def main() -> None:
    """Bucle principal: lee lineas JSON-RPC de stdin y escribe respuestas en stdout."""
    stdin = sys.stdin
    stdout = sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            # Entrada no parseable: error estandar sin id.
            stdout.write(json.dumps(_error(None, -32700, "Parse error")) + "\n")
            stdout.flush()
            continue

        response = handle_request(message)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


if __name__ == "__main__":
    main()
