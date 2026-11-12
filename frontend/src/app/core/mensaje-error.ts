/**
 * Convierte un error de HTTP en un mensaje en lenguaje simple para el Usuario.
 *
 * Solo se muestra el `detail` del backend cuando es un texto: los errores de
 * dominio del backend (422/404/403/429) traen un mensaje en español coloquial
 * pensado para el Usuario y sin PII. Los 422 de validación de FastAPI traen un
 * arreglo en `detail`; esos y cualquier otra forma usan el mensaje por defecto,
 * así nunca se exponen detalles internos (rule-security: errores genéricos).
 */
export function mensajeDeError(error: unknown, porDefecto: string): string {
  const estado = leerEstado(error);
  if (estado === 403) {
    return 'Tu sesión venció. Entra de nuevo para seguir.';
  }
  const detalle = leerDetalle(error);
  return detalle ?? porDefecto;
}

function leerEstado(error: unknown): number | null {
  if (typeof error === 'object' && error !== null && 'status' in error) {
    const valor = (error as { status: unknown }).status;
    return typeof valor === 'number' ? valor : null;
  }
  return null;
}

function leerDetalle(error: unknown): string | null {
  if (typeof error !== 'object' || error === null || !('error' in error)) {
    return null;
  }
  const cuerpo = (error as { error: unknown }).error;
  if (typeof cuerpo !== 'object' || cuerpo === null || !('detail' in cuerpo)) {
    return null;
  }
  const detalle = (cuerpo as { detail: unknown }).detail;
  return typeof detalle === 'string' && detalle.trim().length > 0 ? detalle : null;
}
