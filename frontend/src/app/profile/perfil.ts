/**
 * Lógica pura de PRESENTACIÓN del Perfil de Usuario (Req 9.1, 9.2).
 *
 * Da retroalimentación inmediata en la UI; la validación y la autorización
 * reales son siempre del backend (Profile Service). El catálogo de tipos de
 * actividad y los límites deben coincidir con la allowlist del servidor
 * (`backend/app/profile/constants.py`).
 */

/** Longitud máxima de la zona geográfica (coincide con el backend). */
export const ZONA_MAX_LONGITUD = 100;

/** Dígitos mínimos y máximos del teléfono (coinciden con el backend). */
export const TELEFONO_MIN_DIGITOS = 7;
export const TELEFONO_MAX_DIGITOS = 15;

/** Opción de tipo de cultivo o comercio: valor del backend + etiqueta legible. */
export interface OpcionActividad {
  readonly valor: string;
  readonly etiqueta: string;
}

/**
 * Catálogo de tipos de cultivo o comercio permitidos. El `valor` es el que
 * acepta la allowlist del backend; la `etiqueta` es el texto que ve el Usuario.
 */
export const TIPOS_ACTIVIDAD: readonly OpcionActividad[] = [
  { valor: 'cafe', etiqueta: 'Café' },
  { valor: 'platano', etiqueta: 'Plátano' },
  { valor: 'aguacate', etiqueta: 'Aguacate' },
  { valor: 'cacao', etiqueta: 'Cacao' },
  { valor: 'arroz', etiqueta: 'Arroz' },
  { valor: 'maiz', etiqueta: 'Maíz' },
  { valor: 'ganaderia', etiqueta: 'Ganadería' },
  { valor: 'hortalizas', etiqueta: 'Hortalizas' },
  { valor: 'tienda_barrio', etiqueta: 'Tienda de barrio' },
  { valor: 'panaderia', etiqueta: 'Panadería' },
  { valor: 'miscelanea', etiqueta: 'Miscelánea' },
  { valor: 'fruteria', etiqueta: 'Frutería' },
];

const VALORES_ACTIVIDAD = new Set(TIPOS_ACTIVIDAD.map((o) => o.valor));

/** Devuelve la etiqueta legible de un tipo de actividad, o el propio valor. */
export function etiquetaActividad(valor: string): string {
  return TIPOS_ACTIVIDAD.find((o) => o.valor === valor)?.etiqueta ?? valor;
}

/** `true` si el tipo de actividad pertenece al catálogo permitido. */
export function esActividadValida(valor: string): boolean {
  return VALORES_ACTIVIDAD.has(valor);
}

/** `true` si la zona no está vacía (tras recortar) y no excede el máximo. */
export function esZonaValida(valor: string): boolean {
  const limpio = valor.trim();
  return limpio.length >= 1 && limpio.length <= ZONA_MAX_LONGITUD;
}
