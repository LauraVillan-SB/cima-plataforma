"""Errores de dominio del Conversational Agent Service.

Heredan de `ValidationError` (422) de `app.common.errors`, por lo que el
manejador global los convierte en una respuesta genérica en español coloquial
con Correlation-ID, sin stack trace ni contenido del Usuario. El
`internal_detail` lleva solo códigos de motivo y longitudes, nunca el texto ni
el audio del Usuario (Req 3.9, 9.4).
"""

from __future__ import annotations

from app.chat.constants import TEXT_MAX_LENGTH, VOICE_MAX_SECONDS, VOICE_MIN_SECONDS
from app.common.errors import ValidationError


class MensajeInvalidoError(ValidationError):
    """Mensaje de texto vacío o fuera del límite de longitud (Req 3.2).

    El mensaje público indica el límite permitido. El contenido no se devuelve
    en la respuesta: el cliente lo conserva para que el Usuario lo corrija.
    """

    public_message = (
        f"Tu mensaje debe tener entre 1 y {TEXT_MAX_LENGTH} caracteres. "
        "Revísalo y vuelve a enviarlo."
    )


class NotaDeVozInvalidaError(ValidationError):
    """Nota de Voz con formato, duración o tamaño no soportado (Req 3.4).

    Pide en español coloquial repetir el mensaje e indica el límite de duración
    y los formatos soportados.
    """

    public_message = (
        "No pudimos recibir tu nota de voz. Grábala otra vez: debe durar entre "
        f"{int(VOICE_MIN_SECONDS)} y {int(VOICE_MAX_SECONDS)} segundos y estar "
        "en formato m4a, aac, ogg o mp3."
    )
