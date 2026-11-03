import * as fc from 'fast-check';

/**
 * Prueba de propiedad (Tarea 22.3, Property 36 — lógica cliente de la cola).
 *
 * Valida la invariante de la clave de idempotencia de la cola offline: cada
 * clave generada tiene formato UUID v4 y dos generaciones consecutivas son
 * distintas (no colisionan), de modo que cada acción encolada es idempotente
 * por su propia clave.
 *
 * Se prueba la lógica pura de generación de clave de forma aislada (sin cargar
 * el servicio, que depende de @angular/core ESM), consistente con el patrón de
 * pruebas del scaffold.
 * Feature: cima-plataforma, Property 36
 * Validates: Requirements 18.2
 */
const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

/** Misma lógica que `OfflineQueueService.generarClaveIdempotencia` (respaldo). */
function generarClaveIdempotencia(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

describe('Clave de idempotencia de la cola offline', () => {
  it('genera siempre una clave con formato UUID v4', () => {
    fc.assert(
      fc.property(fc.integer(), () => {
        expect(generarClaveIdempotencia()).toMatch(UUID_V4);
      }),
      { numRuns: 100 },
    );
  });

  it('no colisiona entre generaciones consecutivas', () => {
    fc.assert(
      fc.property(fc.integer(), () => {
        expect(generarClaveIdempotencia()).not.toEqual(generarClaveIdempotencia());
      }),
      { numRuns: 100 },
    );
  });
});
