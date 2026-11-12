/**
 * Clave de idempotencia de la cola offline (Req 18.2, Property 36).
 *
 * Lógica pura (sin Angular) para poder probar con jest el MISMO código que usa
 * `OfflineQueueService`, y no una copia.
 *
 * Cada acción encolada lleva su propio `client_event_id` (UUID v4). El backend
 * aplica el lote de forma idempotente por esa clave, así que reenviar el lote
 * tras un fallo de red no duplica registros.
 */

/** Formato UUID v4 en minúsculas. */
export const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

/** Lo mínimo de `Crypto` que se usa; cualquiera de los dos métodos puede faltar. */
export interface FuenteAleatoria {
  randomUUID?: () => string;
  // `Uint8Array<ArrayBuffer>` (no `SharedArrayBuffer`), como exige `Crypto` en TS 5.9.
  getRandomValues?: (arreglo: Uint8Array<ArrayBuffer>) => unknown;
}

/** `crypto` del entorno, o indefinido si no existe. */
export function cryptoDelEntorno(): FuenteAleatoria | undefined {
  return typeof crypto === 'undefined' ? undefined : crypto;
}

/**
 * Genera un UUID v4 para una acción encolada.
 *
 * 1. `crypto.randomUUID()`: solo existe en contexto seguro (HTTPS) y navegadores
 *    recientes.
 * 2. `crypto.getRandomValues()`: existe en todos los navegadores con Service
 *    Worker, aunque no estén en contexto seguro.
 * 3. `Math.random()` como último recurso: la clave no es un secreto, solo tiene
 *    que no repetirse entre acciones del mismo dispositivo.
 */
export function generarClaveIdempotencia(fuente: FuenteAleatoria | undefined = cryptoDelEntorno()): string {
  if (fuente?.randomUUID) {
    return fuente.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (fuente?.getRandomValues) {
    fuente.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  // RFC 4122 §4.4: versión 4 y variante 10xx.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
