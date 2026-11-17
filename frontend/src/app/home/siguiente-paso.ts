import { ItemRuta, Ruta } from '../aprendizaje/learning.service';

/**
 * Lo que la pantalla de inicio propone hacer ahora. Se deriva del estado que ya
 * calcula el backend para cada cápsula (completada, siguiente, pendiente) y
 * para la ruta (completa, evaluación aprobada); aquí solo se elige qué mostrar.
 */
export type SiguientePaso =
  | { readonly tipo: 'leccion'; readonly ruta: Ruta; readonly item: ItemRuta }
  | { readonly tipo: 'evaluacion'; readonly ruta: Ruta }
  | { readonly tipo: 'completo' }
  | { readonly tipo: 'sin_rutas' };

/** Avance sumado de todas las rutas del Usuario. */
export interface AvanceTotal {
  readonly terminadas: number;
  readonly total: number;
}

function itemSiguiente(ruta: Ruta): ItemRuta | undefined {
  return ruta.items.find((i) => i.status === 'next');
}

/**
 * Elige el siguiente paso, en este orden:
 * 1. la evaluación de una ruta terminada que aún no se aprueba (es lo que la
 *    acerca al certificado);
 * 2. la siguiente lección de una ruta ya empezada;
 * 3. la primera lección de una ruta sin empezar;
 * 4. si todo está aprobado, "completo"; si no hay rutas, "sin_rutas".
 * @param rutas rutas del Usuario con su avance, en el orden que entrega el backend
 * @returns el paso que conviene proponer en el inicio
 */
export function elegirSiguientePaso(rutas: readonly Ruta[]): SiguientePaso {
  if (rutas.length === 0) {
    return { tipo: 'sin_rutas' };
  }
  const porEvaluar = rutas.find((r) => r.completed && !r.assessment_passed);
  if (porEvaluar) {
    return { tipo: 'evaluacion', ruta: porEvaluar };
  }
  const empezada = rutas.find((r) => !r.completed && r.completed_count > 0 && itemSiguiente(r));
  const nueva = empezada ?? rutas.find((r) => !r.completed && itemSiguiente(r));
  const item = nueva ? itemSiguiente(nueva) : undefined;
  if (nueva && item) {
    return { tipo: 'leccion', ruta: nueva, item };
  }
  return { tipo: 'completo' };
}

/**
 * Suma las lecciones terminadas y el total de todas las rutas.
 * @param rutas rutas del Usuario con su avance
 * @returns lecciones terminadas y total
 */
export function sumarAvance(rutas: readonly Ruta[]): AvanceTotal {
  return rutas.reduce<AvanceTotal>(
    (acc, r) => ({ terminadas: acc.terminadas + r.completed_count, total: acc.total + r.total_count }),
    { terminadas: 0, total: 0 },
  );
}
