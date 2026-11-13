"""Adaptador del modelo Gemini para el Agente Conversacional (Tarea 11.4).

Requisitos: 3.3, 3.10, 11.5, 16.1, 16.4. OWASP LLM01 (inyección de prompt) y
A10 (SSRF).

Implementa `GenerativeModel` sobre la API REST de Gemini con `httpx` (ya
aprobado en el proyecto), sin SDK adicional:

- Roles separados: `system` y `developer` van en `systemInstruction`; el texto
  del Usuario va solo en `contents` con rol `user`. Nunca se concatenan
  (OWASP LLM01).
- La API key viaja solo en la cabecera `x-goog-api-key`, nunca en la URL (que
  queda en logs de proxies). El cliente no sigue redirecciones: httpx solo quita
  `Authorization` al cambiar de origen, no las cabeceras personalizadas, así que
  una redirección podría reenviar la key a otro dominio.
- El cliente es el de `app/common/http_client.py`: HTTPS, allowlist de dominios,
  bloqueo de IPs internas y Correlation-ID en cada petición.
- Zero Trust sobre la respuesta: se valida con Pydantic, se descartan las partes
  de "razonamiento" (`thought`) y solo se acepta una respuesta terminada
  (`finishReason == "STOP"`). Cualquier otra cosa lanza `ProveedorIaError`, que
  el circuit breaker cuenta como fallo y el worker resuelve con el respaldo
  seguro.
- Nada de esto registra la key ni el contenido: los errores llevan solo códigos.
"""

from __future__ import annotations

import re

import httpx
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from app.chat.dto import ModelResult
from app.chat.prompt import PromptConversacional
from app.common.http_client import crear_cliente

GEMINI_HOST = "generativelanguage.googleapis.com"
_URL_GENERAR = "https://" + GEMINI_HOST + "/v1beta/models/{modelo}:generateContent"

# El nombre del modelo va en la ruta de la URL: patrón estricto, sin "/" ni "..".
_MODELO_VALIDO = re.compile(r"[a-z0-9][a-z0-9.\-]{0,62}")
# Forma de una API key de Google: sin espacios ni saltos de línea, que permitirían
# inyectar cabeceras. El tope evita aceptar basura enorme.
_KEY_VALIDA = re.compile(r"[A-Za-z0-9_\-.]{20,256}")
# Motivo de fin para el código interno del error, sin copiar texto arbitrario.
_MOTIVO_VALIDO = re.compile(r"[A-Z_]{1,40}")

# Temperatura baja: respuestas educativas consistentes, sin creatividad de más.
_TEMPERATURA = 0.3

# Niveles de razonamiento aceptados. "low" bajó la respuesta de ~7 s a ~3 s en
# las mediciones, con la misma calidad para respuestas educativas cortas.
NIVELES_RAZONAMIENTO = frozenset({"low", "high"})


class ProveedorIaError(Exception):
    """El proveedor de IA no devolvió una respuesta utilizable.

    El mensaje es solo un código interno (p. ej. `gemini_http_429`): nunca la
    key, el prompt ni la respuesta del modelo.
    """


class _Parte(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str | None = None
    # Partes de "razonamiento" del modelo: no son la respuesta para el Usuario.
    thought: bool = False


class _Contenido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    parts: list[_Parte] = []


class _Candidato(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: _Contenido | None = None
    finishReason: str | None = None  # noqa: N815 (nombre del contrato de Gemini)


class _RespuestaGemini(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[_Candidato] = []
    modelVersion: str | None = None  # noqa: N815 (nombre del contrato de Gemini)


class GeminiModel:
    """`GenerativeModel` respaldado por la API de Gemini."""

    def __init__(
        self,
        api_key: str,
        modelo: str,
        *,
        timeout_segundos: float,
        max_output_tokens: int,
        nivel_razonamiento: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Crea el adaptador.

        Args:
            api_key: API key de Gemini (de la configuración, nunca del código).
            modelo: nombre del modelo, p. ej. `gemini-3.8-flash`.
            timeout_segundos: espera máxima de la llamada HTTP.
            max_output_tokens: tope de tokens de la respuesta.
            nivel_razonamiento: `low` o `high`; `None` deja el del modelo.
            transport: solo para pruebas (`httpx.MockTransport`).

        Raises:
            ValueError: si la key, el modelo o el nivel no son válidos. El
                mensaje nunca incluye la key.
        """
        if not isinstance(api_key, str) or not _KEY_VALIDA.fullmatch(api_key):
            raise ValueError("api key de Gemini ausente o con formato invalido")
        if not isinstance(modelo, str) or not _MODELO_VALIDO.fullmatch(modelo):
            raise ValueError("nombre de modelo de Gemini invalido")
        if nivel_razonamiento is not None and nivel_razonamiento not in NIVELES_RAZONAMIENTO:
            raise ValueError("nivel de razonamiento de Gemini invalido")
        self.__api_key = api_key
        self._modelo = modelo
        self._timeout = timeout_segundos
        self._max_output_tokens = max_output_tokens
        self._nivel_razonamiento = nivel_razonamiento
        self._transport = transport

    def __repr__(self) -> str:
        """Representación sin la key, por si el objeto llega a un log o traza."""
        return f"GeminiModel(modelo={self._modelo!r}, api_key='****')"

    def cuerpo(self, prompt: PromptConversacional) -> dict[str, object]:
        """Arma el cuerpo de la petición con cada rol en su campo propio.

        `system` y `developer` van como dos partes de `systemInstruction`; el
        texto del Usuario va solo en `contents`, con rol `user`. El contexto del
        Perfil, si existe, va como una parte aparte del mismo turno `user`, antes
        del mensaje: es información del lado del Usuario, nunca instrucción.
        """
        partes_usuario = [{"text": prompt.contexto}] if prompt.contexto else []
        partes_usuario.append({"text": prompt.user})
        configuracion: dict[str, object] = {
            "temperature": _TEMPERATURA,
            "maxOutputTokens": self._max_output_tokens,
        }
        if self._nivel_razonamiento:
            configuracion["thinkingConfig"] = {"thinkingLevel": self._nivel_razonamiento}
        return {
            "systemInstruction": {
                "parts": [{"text": prompt.system}, {"text": prompt.developer}],
            },
            "contents": [{"role": "user", "parts": partes_usuario}],
            "generationConfig": configuracion,
        }

    async def generate(self, prompt: PromptConversacional) -> ModelResult:
        """Invoca a Gemini y devuelve el texto de la respuesta y su versión.

        Raises:
            ProveedorIaError: respuesta HTTP no exitosa, cuerpo malformado, sin
                candidatos, respuesta incompleta o bloqueada, o texto vacío.
            SsrfBlockedError: el dominio de Gemini no está en la allowlist.
            httpx.HTTPError: fallo de red o timeout.
        """
        url = _URL_GENERAR.format(modelo=self._modelo)
        async with crear_cliente(
            self._transport, timeout=self._timeout, follow_redirects=False
        ) as cliente:
            respuesta = await cliente.post(
                url,
                json=self.cuerpo(prompt),
                headers={"x-goog-api-key": self.__api_key},
            )
        return self._interpretar(respuesta)

    def _interpretar(self, respuesta: httpx.Response) -> ModelResult:
        """Valida la respuesta de Gemini (Zero Trust) y extrae el texto final."""
        if respuesta.status_code != 200:
            # 3xx incluido: no se siguen redirecciones (ver docstring del módulo).
            raise ProveedorIaError(f"gemini_http_{respuesta.status_code}")
        try:
            datos = _RespuestaGemini.model_validate_json(respuesta.content)
        except PydanticValidationError:
            raise ProveedorIaError("gemini_respuesta_malformada") from None
        if not datos.candidates:
            # Sin candidatos: p. ej. el prompt fue bloqueado por el proveedor.
            raise ProveedorIaError("gemini_sin_candidatos")
        candidato = datos.candidates[0]
        if candidato.finishReason != "STOP":
            # MAX_TOKENS deja la respuesta cortada; SAFETY, RECITATION u otros la
            # bloquean. En todos los casos se prefiere el respaldo seguro.
            motivo = candidato.finishReason or "NINGUNO"
            if not _MOTIVO_VALIDO.fullmatch(motivo):
                motivo = "otro"
            raise ProveedorIaError(f"gemini_fin_{motivo.lower()}")
        partes = candidato.content.parts if candidato.content else []
        texto = "".join(p.text for p in partes if p.text and not p.thought).strip()
        if not texto:
            raise ProveedorIaError("gemini_texto_vacio")
        version = datos.modelVersion
        if not version or not _MODELO_VALIDO.fullmatch(version):
            version = self._modelo
        return ModelResult(text=texto, model_version=version)
