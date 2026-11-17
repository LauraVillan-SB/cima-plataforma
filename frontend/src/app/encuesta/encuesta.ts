/**
 * Lógica pura de la Encuesta de Satisfacción (sin Angular) para probarla con jest.
 * La validación real, la redacción de PII del comentario y el registro ocurren en el
 * servidor (Req 20.3–20.5); aquí solo se arma la pantalla y el cuerpo del envío.
 */

/** Largo máximo del comentario, igual al del backend (`COMMENT_MAX_LENGTH`). */
export const COMENTARIO_MAX = 500;

/** Calificación de 1 a 5 con una palabra para quien no lee bien los números. */
export const OPCIONES_CALIFICACION: readonly { readonly valor: number; readonly etiqueta: string }[] = [
  { valor: 1, etiqueta: 'Nada' },
  { valor: 2, etiqueta: 'Poco' },
  { valor: 3, etiqueta: 'Más o menos' },
  { valor: 4, etiqueta: 'Bastante' },
  { valor: 5, etiqueta: 'Mucho' },
];

/** Mensaje si la ruta no tiene encuesta activa (404). */
export const MENSAJE_SIN_ENCUESTA = 'Esta ruta todavía no tiene encuesta. ¡Gracias por querer opinar!';

/** Mensaje sin conexión. */
export const MENSAJE_SIN_CONEXION =
  'Necesitas conexión a internet para enviar tu opinión. Intenta de nuevo cuando tengas señal.';

/** Mensaje genérico ante cualquier otro error. */
export const MENSAJE_GENERICO = 'No pudimos enviar tu opinión. Intenta de nuevo en un momento.';

/** Pregunta tal como la entrega el backend. */
export interface PreguntaEncuesta {
  readonly id: string;
  readonly text: string;
  readonly type: string;
}

/** Cuerpo de `POST /api/v1/encuestas/{rutaId}/respuestas`. */
export interface CuerpoRespuesta {
  readonly client_event_id: string;
  readonly profile_id: string;
  readonly rating: number;
  readonly answers: { readonly comentario?: string };
  readonly geo_zone?: string;
}

/** Primera pregunta de un tipo (`rating` o `text`), o null si la encuesta no la trae. */
export function preguntaDeTipo(
  preguntas: readonly PreguntaEncuesta[],
  tipo: 'rating' | 'text',
): PreguntaEncuesta | null {
  return preguntas.find((p) => p.type === tipo) ?? null;
}

/** Verdadero si la calificación es un entero de 1 a 5. */
export function calificacionValida(valor: number | null): valor is number {
  return valor !== null && Number.isInteger(valor) && valor >= 1 && valor <= 5;
}

/**
 * Arma el cuerpo del envío. El comentario va solo si tiene texto, recortado al
 * máximo; la zona solo si existe. El `client_event_id` se genera una sola vez por
 * pantalla para que reintentar no duplique la respuesta (Req 20.6).
 */
export function armarRespuesta(
  clientEventId: string,
  perfil: { readonly id: string; readonly geo_zone?: string | null },
  calificacion: number,
  comentario: string,
): CuerpoRespuesta {
  const texto = comentario.trim().slice(0, COMENTARIO_MAX);
  const zona = (perfil.geo_zone ?? '').trim();
  return {
    client_event_id: clientEventId,
    profile_id: perfil.id,
    rating: calificacion,
    answers: texto ? { comentario: texto } : {},
    ...(zona ? { geo_zone: zona } : {}),
  };
}

/**
 * Mensaje para el Usuario según la respuesta del backend. Con 409 (ruta sin
 * terminar o ya respondida) y con 422 de texto (comentario con datos personales) el
 * backend trae un mensaje claro; en los demás casos se usa uno propio para no
 * mostrar detalles internos.
 */
export function mensajeError(estado: number, detalle: unknown): string {
  const texto = typeof detalle === 'string' ? detalle.trim() : '';
  if ((estado === 409 || estado === 422) && texto) {
    return texto;
  }
  if (estado === 404) {
    return MENSAJE_SIN_ENCUESTA;
  }
  if (estado === 0) {
    return MENSAJE_SIN_CONEXION;
  }
  return MENSAJE_GENERICO;
}
