import * as fc from 'fast-check';

/**
 * Prueba de logica pura con fast-check (Tarea 2).
 *
 * Valida la invariante del generador de Correlation-ID: produce siempre una
 * cadena con formato UUID v4 (8-4-4-4-12, con el dígito de version 4).
 * Feature: cima-plataforma
 */

const UUID_V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function generarCorrelationId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

describe('Correlation-ID', () => {
  it('genera siempre un UUID v4 valido', () => {
    fc.assert(
      fc.property(fc.integer(), () => {
        expect(generarCorrelationId()).toMatch(UUID_V4);
      }),
      { numRuns: 100 },
    );
  });
});
