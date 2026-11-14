/**
 * Lógica pura del lector de la página (sin Angular ni DOM real) para probarla con jest.
 *
 * El lector toma los bloques de texto visibles del contenido principal (títulos,
 * párrafos, elementos de lista, etiquetas y avisos) y los lee uno a uno con la voz
 * del celular, resaltando el que se está diciendo (Req 13.4, 14.3). Solo lee texto que
 * ya está en pantalla; no envía nada a ningún servidor.
 */

/** Etiquetas de los bloques que se leen, en el orden en que aparecen. */
export const SELECTOR_BLOQUES = 'h1, h2, h3, p, li, label, .sb-ui-alert';

/** Partes que nunca se leen: ocultas, solo para lector de pantalla o marcadas a propósito. */
export const SELECTOR_EXCLUIDOS = '[hidden], [aria-hidden="true"], .solo-lector, [data-no-leer]';

/**
 * Deja solo los bloques "hoja" con texto, en su orden: si un bloque contiene a otro
 * seleccionado (por ejemplo, un elemento de lista con un párrafo adentro), se lee solo
 * el de adentro, para no decir lo mismo dos veces.
 *
 * @param texto devuelve el texto visible de un bloque.
 * @param contiene indica si el primer bloque contiene al segundo.
 */
export function bloquesALeer<T>(
  bloques: readonly T[],
  texto: (bloque: T) => string,
  contiene: (padre: T, hijo: T) => boolean,
): T[] {
  return bloques.filter(
    (bloque) =>
      texto(bloque).trim().length > 0 &&
      !bloques.some((otro) => otro !== bloque && contiene(bloque, otro)),
  );
}
