/** Etiqueta legible en español coloquial de cada tema de microcápsula (Req 4.2). */
const ETIQUETA_TEMA: Readonly<Record<string, string>> = {
  gestion_riesgos: 'Gestión de riesgos',
  finanzas: 'Finanzas',
  adaptacion_clima: 'Adaptación al clima',
};

/**
 * Devuelve la etiqueta en español de un tema; si no está en el catálogo
 * conocido, devuelve el código tal cual para no ocultar contenido.
 * @param topic código del tema entregado por el backend
 * @returns etiqueta legible
 */
export function etiquetaTema(topic: string): string {
  return ETIQUETA_TEMA[topic] ?? topic;
}

/**
 * Convierte segundos en minutos redondeados, con mínimo de 1.
 * @param segundos duración en segundos
 * @returns minutos enteros (al menos 1)
 */
export function minutos(segundos: number): number {
  return Math.max(1, Math.round(segundos / 60));
}
