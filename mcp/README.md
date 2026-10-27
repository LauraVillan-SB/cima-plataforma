# MCP propio del proyecto — `cima-project`

Servidor MCP (Model Context Protocol) propio de **CIMA**, con herramientas de dominio
alineadas con el spec en `.kiro/specs/cima-plataforma/`. Complementa los MCP
institucionales (`security-audit`, `datadog`, `cloudwatch`, `aws-api`) configurados a
nivel usuario, sin reemplazarlos.

## ¿Por qué un MCP propio?

Los MCP de la compañía son transversales (seguridad, observabilidad, AWS). Este MCP
expone **reglas de negocio específicas de CIMA** como herramientas que Kiro puede invocar
durante el desarrollo, para que el código generado respete los requisitos desde el primer
momento.

## Herramientas

| Herramienta | Qué hace | Requisito |
|---|---|---|
| `validate_user_profile` | Valida un Perfil de Usuario (campos permitidos, teléfono 7–15 dígitos, tipo en allowlist, zona ≤ 100 chars) | R9 |
| `validate_clave` | Valida la Clave de 4 dígitos y, opcionalmente, su confirmación. No almacena la Clave | R1 |
| `mask_pii` | Enmascara PII dejando visibles como máximo los últimos N caracteres | R5.9 / R9.4 |
| `list_requirements` | Lista los títulos de los 20 requisitos del spec para trazabilidad | — |

## Diseño y seguridad

- **Sin dependencias externas:** implementa JSON-RPC 2.0 por stdio con solo la librería
  estándar de Python. No requiere `uv`, `pip install` ni acceso a JFrog.
- **Sin red ni secretos:** toda la lógica es local y determinista. No abre conexiones ni
  lee credenciales.
- **Sin PII en salidas:** `validate_clave` solo devuelve `valid`/`errors`; nunca la Clave.
- **Allowlist sobre blocklist:** los tipos de actividad válidos están en una lista cerrada.
- **Ruta fija de solo lectura:** `list_requirements` lee un archivo fijo del proyecto; no
  acepta rutas del usuario (sin path traversal).

## Configuración

Registrado en `.kiro/settings/mcp.json` (nivel workspace):

```json
{
  "mcpServers": {
    "cima-project": {
      "command": "python3",
      "args": ["mcp/cima_mcp_server.py"],
      "disabled": false,
      "autoApprove": ["validate_user_profile", "validate_clave", "mask_pii", "list_requirements"]
    }
  }
}
```

## Prueba manual (sin Kiro)

Se puede verificar el servidor por stdio enviando mensajes JSON-RPC:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"mask_pii","arguments":{"value":"3001234567"}}}' \
  | python3 mcp/cima_mcp_server.py
```

Salida esperada para `mask_pii`: `{"masked": "******4567", "visible_chars": 4}`.

## Uso desde Kiro

Tras reconectar el servidor MCP (vista "MCP Server" en el panel de Kiro, o reinicio de
sesión), se puede pedir en el chat, por ejemplo:

> "Valida este perfil con la herramienta del MCP de CIMA: teléfono 3001234567, cultivo café, zona Huila."

Kiro invocará `validate_user_profile` y devolverá el resultado estructurado.
