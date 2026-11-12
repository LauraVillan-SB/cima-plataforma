/**
 * Regla pura (sin Angular) que decide cuándo renovar la sesión, para probarla con jest.
 *
 * El backend renueva la sesión en cada petición autenticada y la invalida tras
 * 30 min sin actividad (Req 1.14). Entre los 15 y los 30 min el access ya venció
 * (403) pero el refresh sigue vigente: el cliente lo usa una sola vez para
 * renovar sin pedir la Clave (Req 2.6). Si el refresco también falla, la sesión
 * expiró y hay que volver a entrar.
 */

/** Ruta que renueva la sesión con el refresh token. */
export const RUTA_REFRESCO = '/api/v1/auth/refresco';

/**
 * Rutas de autenticación donde un error no significa "sesión vencida": las de
 * ingreso y registro no tienen sesión aún, y refresco y salir son las que la
 * gestionan (reintentarlas daría un ciclo).
 */
const RUTAS_SIN_REFRESCO: readonly string[] = [
  '/api/v1/auth/ingreso',
  '/api/v1/auth/registro',
  RUTA_REFRESCO,
  '/api/v1/auth/salir',
];

/** Estado HTTP con el que el backend rechaza una sesión ausente o vencida. */
const SESION_RECHAZADA = 403;

/**
 * Verdadero si ante este error conviene renovar la sesión y repetir la petición.
 *
 * Solo para peticiones RELATIVAS a la API propia (`/api/...`): una URL absoluta,
 * aunque su ruta empiece por `/api/`, apunta a otro origen y no se toca. Además
 * el error debe ser 403, la ruta no debe ser de las de autenticación de arriba y
 * la petición no debe haberse reintentado ya (una sola vez, para no entrar en
 * ciclo cuando el 403 es de autorización y no de sesión).
 */
export function debeIntentarRefresco(url: string, estado: number, yaReintentada: boolean): boolean {
  if (yaReintentada || estado !== SESION_RECHAZADA || !url.startsWith('/api/')) {
    return false;
  }
  const camino = url.split(/[?#]/, 1)[0];
  return !RUTAS_SIN_REFRESCO.includes(camino);
}
