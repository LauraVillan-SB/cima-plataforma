"""Constantes de dominio del Conversational Agent Service.

Define los límites de validación de la entrada del Usuario antes de invocar
STT o el modelo de IA generativa: longitud del mensaje de texto, formatos de
audio permitidos (allowlist), duración y tamaño máximo de la Nota de Voz.
Requisitos: 3.2, 3.4.
"""

from __future__ import annotations

# Longitud permitida del mensaje de texto, contada tras normalizar y hacer trim
# (Req 3.1, 3.2).
TEXT_MIN_LENGTH = 1
TEXT_MAX_LENGTH = 2000

# Duración permitida de la Nota de Voz en segundos, ambos extremos incluidos
# (Req 3.3, 3.4).
VOICE_MIN_SECONDS = 1.0
VOICE_MAX_SECONDS = 120.0

# Allowlist de formatos de audio soportados (Req 3.3, 3.4). "m4a/aac" del
# requisito se acepta en ambas variantes: contenedor MP4 (m4a) y flujo ADTS (aac).
ALLOWED_AUDIO_FORMATS: frozenset[str] = frozenset({"m4a", "aac", "ogg", "mp3"})

# Tamaño máximo de la Nota de Voz. 120 s a 320 kbps (tope de mp3) ocupan ~4,7 MB;
# 5 MiB cubre ese caso y limita el abuso por cargas grandes (rule-security).
VOICE_MAX_BYTES = 5 * 1024 * 1024

# Bytes mínimos de cabecera necesarios para identificar el formato real.
AUDIO_HEADER_MIN_BYTES = 12

# Marcas ("brands") del contenedor MP4 aceptadas como audio m4a.
M4A_BRANDS: frozenset[bytes] = frozenset({b"M4A ", b"M4B ", b"mp42", b"isom"})


# --- Inferencia asíncrona (Tarea 11.3, Req 3.5-3.8, 12.4) -------------------

# Estados del ciclo de vida de una inferencia encolada.
ESTADO_ENCOLADO = "encolado"
ESTADO_PROCESANDO = "procesando"
ESTADO_LISTO = "listo"
ESTADO_ERROR = "error"

# Umbral tras el cual el cliente debe mostrar un indicador de procesamiento
# (Req 3.7): la respuesta deberia llegar antes de 15 s.
PROCESSING_INDICATOR_SECONDS = 15

# Tiempo maximo de espera de una inferencia (Req 3.8): superado, se marca error
# de servicio no disponible conservando el historial.
INFERENCE_TIMEOUT_SECONDS = 60


# --- Voz: STT/TTS (Tarea 11.4, Req 14.2, 14.3, 14.5) -----------------------

# Canal de entrada por voz (el de texto es "texto", en service.py).
CANAL_VOZ = "voz"

# Umbral de confianza del STT en [0, 1]: por debajo, se pide al Usuario repetir
# en lenguaje simple sin atribuirle el error (Req 14.5).
STT_CONFIDENCE_THRESHOLD = 0.6

# Estado cuando la transcripción no es suficientemente confiable: el cliente
# debe pedir al Usuario que repita el mensaje de voz (Req 14.5).
ESTADO_REPETIR_VOZ = "repetir_voz"


# --- Guardrails, validación de salida y kill switch (Tarea 11.5, Req 16) ---

# Decisiones del guardrail, registradas de forma auditable (Req 16.4).
GUARDRAIL_PERMITIDO = "permitido"
GUARDRAIL_BLOQUEO_ENTRADA = "bloqueo_entrada"
GUARDRAIL_SALIDA_NO_VALIDADA = "salida_no_validada"
GUARDRAIL_DERIVADO = "derivado_humano"
GUARDRAIL_KILL_SWITCH = "kill_switch"

# Marca reconocible de que responde una IA (Req 16.5). Se antepone a la respuesta.
AI_DISCLOSURE_PREFIX = "🤖 Asistente de CIMA (IA): "

# Respuesta segura de respaldo cuando se deriva o se degrada el agente (Req 16.3, 16.6).
SAFE_FALLBACK_RESPONSE = (
    "Para darte una respuesta segura, voy a conectarte con una persona del "
    "equipo de CIMA. También puedes intentarlo de nuevo más tarde."
)

# Patrones de temas fuera de dominio o inseguros que se bloquean en la entrada
# (Req 16.1). Allowlist de dominio: CIMA educa en finanzas, riesgos y clima; se
# bloquea lo que induzca decisiones financieras indebidas o quede fuera de ámbito.
BLOCKED_INPUT_PATTERNS: tuple[str, ...] = (
    r"\bgaranti[az]\w*\s+(ganancia|retorno|rentabilidad)",
    r"\binvierte?\s+todo\b",
    r"\bpr[eé]stamo\s+gota\s+a\s+gota\b",
    # "una?" cubre el artículo femenino ("cómo fabricar una bomba") (Req 3.4).
    r"\bc[oó]mo\s+(fabricar|hacer)\s+(una?\s+)?(arma|explosivo|bomba)",
)

# Marcadores de oferta que SÍ pueden respaldarse con el catálogo de Microseguros
# (Req 16.2). Los demás marcadores (incentivo, descuento, ...) nunca se respaldan.
CATALOG_BACKED_OFFER_MARKERS: tuple[str, ...] = ("microseguro",)

# Cifras de precio o porcentaje: el catálogo no tiene precios, por lo que una
# oferta con cifras se considera inventada (Req 16.2).
OFFER_FIGURES_PATTERN = r"\$\s*\d|\d\s*%|\b\d[\d.,]*\s+(pesos|cop)\b"

# Palabras que marcan una oferta/incentivo en la salida del modelo: si aparecen,
# la respuesta debe validarse contra el backend antes de presentarla (Req 16.2).
OFFER_OUTPUT_MARKERS: tuple[str, ...] = (
    "microseguro",
    "incentivo",
    "descuento",
    "beneficio",
    "promoci",
    # Incentivos dichos con otras palabras (Property 39): sin estos, una salida
    # como "te damos un bono de 50.000 pesos" pasaba sin validarse. Se buscan por
    # INICIO de palabra y sin tildes (ver guardrails), así "abono" no es "bono".
    "bono",
    "bonific",
    "regal",
    "gratis",
    "gratuit",
    "rebaja",
    "premio",
    "cupon",
)

# Temas sensibles que derivan a canal humano / respuesta segura (Req 16.3).
SENSITIVE_TOPIC_PATTERNS: tuple[str, ...] = (
    r"\bsuicid\w*\b",
    r"\bviolencia\s+(intrafamiliar|dom[eé]stica)\b",
    r"\bamenaza\w*\s+de\s+muerte\b",
)
