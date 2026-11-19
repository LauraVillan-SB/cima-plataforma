/**
 * Lógica pura de la pantalla del Certificado (sin Angular) para probarla con jest.
 * Solo da forma a lo que entrega el backend: la emisión, la autorización y el
 * enmascaramiento ocurren siempre en el servidor (Req 6, 9.4).
 */

/** Zona horaria de Colombia: la fecha del certificado se muestra en hora local. */
const ZONA_COLOMBIA = 'America/Bogota';

/** Tamaño de los grupos del código para leerlo o dictarlo sin equivocarse. */
const TAMANO_GRUPO = 4;

/** Mensaje si el certificado no se encuentra o no es del Usuario (Req 6.6, 6.7). */
export const MENSAJE_NO_ENCONTRADO =
  'No encontramos su certificado. Revise que haya aprobado la evaluación de esta ruta.';

/** Mensaje sin conexión: el certificado no se guarda en el celular a propósito. */
export const MENSAJE_SIN_CONEXION =
  'Necesita conexión a internet para ver su certificado. Intente de nuevo cuando tenga señal.';

/** Mensaje genérico ante cualquier otro error. */
export const MENSAJE_GENERICO = 'No pudimos cargar su certificado. Intente de nuevo en un momento.';

/**
 * Fecha de emisión legible en español de Colombia ("14 de noviembre de 2026").
 * Si la fecha no es válida devuelve cadena vacía y la pantalla no la muestra.
 */
export function fechaCertificado(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('es-CO', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: ZONA_COLOMBIA,
  }).format(fecha);
}

/** Código de verificación en grupos de 4 ("ABCD EFGH ...") solo para mostrarlo. */
export function codigoLegible(codigo: string): string {
  const limpio = codigo.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
  return (limpio.match(new RegExp(`.{1,${TAMANO_GRUPO}}`, 'g')) ?? []).join(' ');
}

/** Últimos 4 dígitos del celular ya enmascarado por el backend, o cadena vacía. */
export function finalCelular(enmascarado: string | null | undefined): string {
  const visibles = (enmascarado ?? '').replace(/\*/g, '');
  return /^\d{1,4}$/.test(visibles) ? visibles : '';
}

/**
 * Mensaje para el Usuario según la respuesta del backend.
 *
 * Con 409 el backend ya trae un mensaje claro (falta terminar la ruta o el puntaje
 * mínimo, Req 6.2); en los demás casos se usa un mensaje propio para no mostrar
 * detalles internos.
 */
export function mensajeError(estado: number, detalle: unknown): string {
  if (estado === 409 && typeof detalle === 'string' && detalle.trim()) {
    return detalle.trim();
  }
  if (estado === 403 || estado === 404) {
    return MENSAJE_NO_ENCONTRADO;
  }
  if (estado === 0) {
    return MENSAJE_SIN_CONEXION;
  }
  return MENSAJE_GENERICO;
}
