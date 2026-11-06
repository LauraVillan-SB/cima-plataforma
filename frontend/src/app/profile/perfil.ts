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

/**
 * Opción de tipo de cultivo o comercio: valor del backend, etiqueta legible y
 * la frase con la que se nombra a la persona en los saludos ("tu cultivo de
 * café", "tu tienda de barrio"). La frase es propia de cada opción porque no
 * todo es un cultivo (p. ej. la ganadería o los comercios).
 */
export interface OpcionActividad {
  readonly valor: string;
  readonly etiqueta: string;
  readonly frase: string;
}

/**
 * Catálogo de tipos de cultivo o comercio permitidos. El `valor` es el que
 * acepta la allowlist del backend; la `etiqueta` es el texto que ve el Usuario.
 */
export const TIPOS_ACTIVIDAD: readonly OpcionActividad[] = [
  { valor: 'cafe', etiqueta: 'Café', frase: 'tu cultivo de café' },
  { valor: 'platano', etiqueta: 'Plátano', frase: 'tu cultivo de plátano' },
  { valor: 'aguacate', etiqueta: 'Aguacate', frase: 'tu cultivo de aguacate' },
  { valor: 'cacao', etiqueta: 'Cacao', frase: 'tu cultivo de cacao' },
  { valor: 'arroz', etiqueta: 'Arroz', frase: 'tu cultivo de arroz' },
  { valor: 'maiz', etiqueta: 'Maíz', frase: 'tu cultivo de maíz' },
  { valor: 'ganaderia', etiqueta: 'Ganadería', frase: 'tu ganadería' },
  { valor: 'hortalizas', etiqueta: 'Hortalizas', frase: 'tu cultivo de hortalizas' },
  { valor: 'tienda_barrio', etiqueta: 'Tienda de barrio', frase: 'tu tienda de barrio' },
  { valor: 'panaderia', etiqueta: 'Panadería', frase: 'tu panadería' },
  { valor: 'miscelanea', etiqueta: 'Miscelánea', frase: 'tu miscelánea' },
  { valor: 'fruteria', etiqueta: 'Frutería', frase: 'tu frutería' },
];

const VALORES_ACTIVIDAD = new Set(TIPOS_ACTIVIDAD.map((o) => o.valor));

/** Devuelve la etiqueta legible de un tipo de actividad, o el propio valor. */
export function etiquetaActividad(valor: string): string {
  return TIPOS_ACTIVIDAD.find((o) => o.valor === valor)?.etiqueta ?? valor;
}

/**
 * Frase para nombrar la actividad en un saludo ("tu cultivo de café"). Si el
 * valor no está en el catálogo devuelve un texto neutro, nunca el valor crudo.
 */
export function fraseActividad(valor: string): string {
  return TIPOS_ACTIVIDAD.find((o) => o.valor === valor)?.frase ?? 'tu actividad';
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
