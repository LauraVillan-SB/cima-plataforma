import * as fc from 'fast-check';

import { FuenteAleatoria, UUID_V4, generarClaveIdempotencia } from './idempotencia';

/**
 * Prueba de propiedad (Tarea 22.3, Property 36 — lógica cliente de la cola).
 *
 * Valida la clave de idempotencia de la cola offline sobre el MISMO código que
 * usa `OfflineQueueService` (`idempotencia.ts`), no sobre una copia: antes esta
 * prueba repetía la función dentro del test, así que un cambio en el servicio no
 * se detectaba. Se cubren los tres caminos de generación: `randomUUID`,
 * `getRandomValues` y el último recurso sin `crypto`.
 *
 * Feature: cima-plataforma, Property 36
 * Validates: Requirements 18.2
 */

/** Fuente con solo `getRandomValues`, alimentada por bytes que elige fast-check. */
function fuenteConBytes(bytes: number[]): FuenteAleatoria {
  return {
    getRandomValues: (arreglo: Uint8Array<ArrayBuffer>) => {
      arreglo.set(bytes.slice(0, arreglo.length));
      return arreglo;
    },
  };
}

const CAMINOS: ReadonlyArray<[string, () => FuenteAleatoria | undefined]> = [
  ['randomUUID', () => ({ randomUUID: () => crypto.randomUUID() })],
  ['getRandomValues', () => ({ getRandomValues: (a: Uint8Array<ArrayBuffer>) => crypto.getRandomValues(a) })],
  ['sin crypto (último recurso)', () => undefined],
];

describe('Clave de idempotencia de la cola offline (Property 36)', () => {
  it('con cualquier secuencia de bytes aleatorios, la clave es un UUID v4 válido', () => {
    fc.assert(
      fc.property(fc.array(fc.integer({ min: 0, max: 255 }), { minLength: 16, maxLength: 16 }), (bytes) => {
        expect(generarClaveIdempotencia(fuenteConBytes(bytes))).toMatch(UUID_V4);
      }),
      { numRuns: 500 },
    );
  });

  it('bytes distintos producen claves distintas (fuera de los bits de versión y variante)', () => {
    const byte = fc.integer({ min: 0, max: 255 });
    const bytes16 = fc.array(byte, { minLength: 16, maxLength: 16 });
    fc.assert(
      fc.property(bytes16, bytes16, (a, b) => {
        // Los bits que fija RFC 4122 (versión en el byte 6, variante en el 8) no cuentan.
        const util = (x: number[]) => x.map((v, i) => (i === 6 ? v & 0x0f : i === 8 ? v & 0x3f : v));
        fc.pre(util(a).join() !== util(b).join());
        expect(generarClaveIdempotencia(fuenteConBytes(a))).not.toEqual(
          generarClaveIdempotencia(fuenteConBytes(b)),
        );
      }),
      { numRuns: 300 },
    );
  });

  it.each(CAMINOS)('camino %s: genera UUID v4 sin repetir en un lote', (_nombre, fuente) => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 200 }), (cantidad) => {
        const claves = Array.from({ length: cantidad }, () => generarClaveIdempotencia(fuente()));
        claves.forEach((clave) => expect(clave).toMatch(UUID_V4));
        expect(new Set(claves).size).toBe(claves.length);
      }),
      { numRuns: 50 },
    );
  });

  it('prefiere randomUUID cuando existe', () => {
    const fuente: FuenteAleatoria = {
      randomUUID: () => '11111111-1111-4111-8111-111111111111',
      getRandomValues: () => {
        throw new Error('no debía usarse');
      },
    };
    expect(generarClaveIdempotencia(fuente)).toBe('11111111-1111-4111-8111-111111111111');
  });
});
