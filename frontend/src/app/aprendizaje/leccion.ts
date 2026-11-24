/**
 * Lógica pura de la pantalla de lección (sin Angular), para probarla con Jest.
 */

/** Ícono de cada estado de una cápsula en "Mi ruta" (decorativo: el estado va en texto). */
const ICONO_ESTADO: Readonly<Record<string, string>> = {
  completed: 'fa-check',
  next: 'fa-play',
  pending: 'fa-lock',
};

/**
 * Clase de Font Awesome para el estado de una cápsula; un estado desconocido
 * usa el de pendiente para no mostrar algo como disponible por error.
 */
export function iconoDeEstado(estado: string): string {
  return Object.prototype.hasOwnProperty.call(ICONO_ESTADO, estado)
    ? ICONO_ESTADO[estado]
    : ICONO_ESTADO['pending'];
}

/** Lo que se muestra arriba del texto completo de la lección. */
export interface ContenidoVisible {
  readonly tieneVideo: boolean;
  readonly resumen: string | null | undefined;
  readonly puntosClave: readonly string[];
}

/**
 * Indica si el acordeón "¿Quiere conocer más?" debe arrancar abierto.
 *
 * El texto completo arranca cerrado para que la lección no se vea densa: arriba
 * quedan el video, el resumen y "Lo más importante". Si la cápsula no trae nada
 * de eso, cerrar el texto dejaría la lección vacía, así que arranca abierto.
 */
export function abrirTextoDeEntrada(contenido: ContenidoVisible): boolean {
  const hayResumen = (contenido.resumen ?? '').trim().length > 0;
  return !contenido.tieneVideo && !hayResumen && contenido.puntosClave.length === 0;
}
