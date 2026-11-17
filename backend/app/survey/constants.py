"""Constantes de dominio del Survey Service.

Define el rango permitido de la calificación (escala 1–5), el marcador de zona
no clasificada y el umbral de k-anonimato para la supresión en reportes
agregados, consistente con el Metrics Service.
Requisitos: 20.3, 20.5, 20.7.
"""

from __future__ import annotations

# Escala de calificación permitida para la Encuesta de Satisfacción (Req 20.3).
RATING_MIN = 1
RATING_MAX = 5

# Marcador para respuestas sin zona geográfica (consistente con Metrics).
UNCLASSIFIED_ZONE = "sin_zona"

# Longitud máxima de la zona geográfica (consistente con el resto del dominio).
GEO_ZONE_MAX_LENGTH = 100

# Umbral de k-anonimato: se suprimen zonas con menos de este número de
# Usuarios distintos para evitar la reidentificación (Req 20.7).
K_ANONYMITY_THRESHOLD = 5

# Comentario libre opcional: largo máximo. Se redacta la PII antes de guardarlo
# (Req 20.5); es la única respuesta abierta de la encuesta.
COMMENT_MAX_LENGTH = 500

# Tipos de pregunta que entiende la pantalla: la calificación va en `rating` y el
# comentario en `answers.comentario`.
QUESTION_TYPE_RATING = "rating"
QUESTION_TYPE_TEXT = "text"

# Encuesta estándar de cada ruta (Req 20.1): breve, opcional y en español
# coloquial, con una calificación de 1 a 5 y un comentario opcional. Texto de
# referencia pendiente de revisión de la Escuela.
SURVEY_QUESTIONS: tuple[dict[str, str], ...] = (
    {
        "id": "calificacion",
        "text": "¿Qué tanto te sirvió esta ruta? Elige de 1 a 5: 1 es nada y 5 es mucho.",
        "type": QUESTION_TYPE_RATING,
    },
    {
        "id": "comentario",
        "text": (
            "Si quieres, cuéntanos qué te gustó o qué podemos mejorar. "
            "No escribas tu nombre, tu celular ni otros datos personales."
        ),
        "type": QUESTION_TYPE_TEXT,
    },
)
