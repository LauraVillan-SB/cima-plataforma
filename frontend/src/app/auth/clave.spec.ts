import * as fc from 'fast-check';

import { esClaveValida, normalizarTelefono } from './clave';

/**
 * Pruebas de propiedad (fast-check) de la validación de presentación de la
 * Clave y del teléfono (Tarea 23).
 * Feature: cima-plataforma
 */
describe('Validacion de Clave y telefono', () => {
  it('acepta exactamente 4 digitos', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 9999 }), (n) => {
        const clave = n.toString().padStart(4, '0');
        expect(esClaveValida(clave)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it('rechaza longitudes distintas de 4', () => {
    fc.assert(
      fc.property(
        fc
          .string({ unit: fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') })
          .filter((s) => s.length !== 4),
        (valor) => {
          expect(esClaveValida(valor)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('rechaza claves con caracteres no numericos', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 4, maxLength: 4 }).filter((s) => !/^\d{4}$/.test(s)),
        (valor) => {
          expect(esClaveValida(valor)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('normaliza el telefono dejando solo digitos y un + inicial opcional', () => {
    expect(normalizarTelefono('  300 123 4567 ')).toBe('3001234567');
    expect(normalizarTelefono('+57 300-123-4567')).toBe('+573001234567');
  });
});
