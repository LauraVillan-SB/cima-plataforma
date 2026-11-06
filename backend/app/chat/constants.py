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
