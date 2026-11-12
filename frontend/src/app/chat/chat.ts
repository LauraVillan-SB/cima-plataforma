/**
 * Lógica pura del chat (sin Angular) para poder probarla con jest.
 *
 * Los tiempos y estados reflejan el contrato del backend: el cliente muestra un
 * indicador de espera pasados `processing_after_seconds` (15 s, Req 3.7) y da la
 * inferencia por fallida a los 60 s (Req 3.8). Las validaciones de aquí son solo
 * ayuda de presentación; el servidor valida SIEMPRE (Req 3.2, 3.4).
 */

/** Estados que devuelve el backend para una inferencia. */
export const ESTADO_LISTO = 'listo';
export const ESTADO_ERROR = 'error';
export const ESTADO_REPETIR_VOZ = 'repetir_voz';

/** Segundos tras los cuales la espera se considera agotada (Req 3.8). */
export const TIEMPO_MAXIMO_SEGUNDOS = 60;

/** Límites del mensaje de texto, contados tras recortar espacios (Req 3.2). */
export const TEXTO_MIN = 1;
export const TEXTO_MAX = 2000;

/** Límites de la nota de voz en segundos, ambos incluidos (Req 3.4). */
export const VOZ_MIN_SEGUNDOS = 1;
export const VOZ_MAX_SEGUNDOS = 120;

/** Fase visible para el Usuario de un mensaje enviado. */
export type FaseChat =
  | 'esperando'
  | 'procesando_lento'
  | 'listo'
  | 'error'
  | 'repetir_voz'
  | 'tiempo_agotado';

/** Verdadero cuando el estado ya no cambiará y se debe dejar de consultar. */
export function esEstadoFinal(estado: string): boolean {
  return estado === ESTADO_LISTO || estado === ESTADO_ERROR || estado === ESTADO_REPETIR_VOZ;
}

/**
 * Decide qué mostrar según el estado del backend y el tiempo de espera.
 * Cualquier estado que no sea final (encolado, procesando u otro desconocido)
 * se trata como "en curso" para no romper si el backend agrega estados.
 */
export function faseDeChat(
  estado: string,
  segundosEsperando: number,
  umbralIndicador: number,
  limite: number = TIEMPO_MAXIMO_SEGUNDOS,
): FaseChat {
  if (estado === ESTADO_LISTO) {
    return 'listo';
  }
  if (estado === ESTADO_ERROR) {
    return 'error';
  }
  if (estado === ESTADO_REPETIR_VOZ) {
    return 'repetir_voz';
  }
  if (segundosEsperando >= limite) {
    return 'tiempo_agotado';
  }
  if (segundosEsperando >= umbralIndicador) {
    return 'procesando_lento';
  }
  return 'esperando';
}

/** El texto se puede enviar si tiene entre 1 y 2000 caracteres tras recortar. */
export function textoValido(texto: string): boolean {
  const largo = texto.trim().length;
  return largo >= TEXTO_MIN && largo <= TEXTO_MAX;
}

/** La nota de voz se puede enviar si dura entre 1 y 120 segundos. */
export function duracionVozValida(segundos: number): boolean {
  return Number.isFinite(segundos) && segundos >= VOZ_MIN_SEGUNDOS && segundos <= VOZ_MAX_SEGUNDOS;
}

/**
 * Formatos que el servidor acepta (m4a, aac, ogg, mp3), en orden de preferencia.
 * El servidor los identifica por su contenido real, no por la extensión.
 */
const MIMES_PREFERIDOS: readonly string[] = [
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/ogg',
  'audio/mpeg',
];

/**
 * Elige el primer formato de grabación que el navegador soporta y el servidor
 * acepta. Devuelve null si no hay ninguno (por ejemplo Chrome solo graba webm),
 * y entonces la interfaz ofrece solo texto en vez de enviar un audio que el
 * servidor rechazaría.
 */
export function elegirMimeAudio(esSoportado: (mime: string) => boolean): string | null {
  for (const mime of MIMES_PREFERIDOS) {
    if (esSoportado(mime)) {
      return mime;
    }
  }
  return null;
}

/** Extensión de archivo para el formato elegido (solo informativa para el servidor). */
export function extensionDeMime(mime: string): string {
  if (mime.startsWith('audio/mp4')) {
    return 'm4a';
  }
  if (mime.startsWith('audio/ogg')) {
    return 'ogg';
  }
  return 'mp3';
}
