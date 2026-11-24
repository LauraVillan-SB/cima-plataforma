/**
 * Lógica pura del ranking (sin Angular), para probarla con Jest.
 *
 * El backend solo entrega alias seudónimos ("Participante 7599"): el Perfil no
 * guarda nombres (Req 9.1). El nombre que la persona escribió en "Mi perfil" vive
 * solo en su celular (`core/trato.ts`), así que se puede mostrar en SU fila, en su
 * propia pantalla, sin enviarlo al servidor. Las demás personas siguen con su alias.
 */

/**
 * Texto de la columna "Participante".
 *
 * @param alias alias seudónimo que entrega el backend
 * @param esUsted si la fila es la de la persona con sesión
 * @param comoLlamar cómo quiere que le digan ("doña Patricia"), ya validado al
 *   leerlo del celular; vacío o `null` si no lo ha dicho
 * @returns el nombre propio con "(usted)" en la fila propia si lo hay; si no, el alias
 */
export function nombreEnRanking(
  alias: string,
  esUsted: boolean,
  comoLlamar: string | null | undefined,
): string {
  if (!esUsted) {
    return alias;
  }
  const nombre = (comoLlamar ?? '').trim();
  return nombre ? `${nombre} (usted)` : `${alias} (usted)`;
}
