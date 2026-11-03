/**
 * Validación de formato de la Clave de 4 dígitos en el cliente (Req 1.4).
 *
 * Es validación de PRESENTACIÓN para dar retroalimentación inmediata al
 * Usuario; la validación y autorización reales son siempre del backend. La
 * Clave debe ser exactamente 4 dígitos numéricos.
 */

/** Longitud exacta requerida de la Clave. */
export const CLAVE_LONGITUD = 4;

/** `true` si el valor es exactamente 4 dígitos numéricos (0-9). */
export function esClaveValida(valor: string): boolean {
  return new RegExp(`^\\d{${CLAVE_LONGITUD}}$`).test(valor);
}

/** Normaliza el teléfono dejando solo dígitos (y un '+' inicial opcional). */
export function normalizarTelefono(valor: string): string {
  const trimmed = valor.trim();
  const masInicial = trimmed.startsWith('+') ? '+' : '';
  return masInicial + trimmed.replace(/[^\d]/g, '');
}
