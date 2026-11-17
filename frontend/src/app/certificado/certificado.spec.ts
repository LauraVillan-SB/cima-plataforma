import * as fc from 'fast-check';

import {
  MENSAJE_GENERICO,
  MENSAJE_NO_ENCONTRADO,
  MENSAJE_SIN_CONEXION,
  codigoLegible,
  fechaCertificado,
  finalCelular,
  mensajeError,
} from './certificado';

/**
 * Pruebas de la lógica pura de la pantalla del Certificado (Req 6.2, 6.3, 6.6, 9.4).
 * Feature: cima-plataforma
 */
describe('fechaCertificado', () => {
  it('muestra la fecha en español y en hora de Colombia', () => {
    // 03:00 UTC del 14 es todavía el 13 en Colombia (UTC-5).
    expect(fechaCertificado('2026-11-14T03:00:00+00:00')).toBe('13 de noviembre de 2026');
    expect(fechaCertificado('2026-11-14T15:00:00+00:00')).toBe('14 de noviembre de 2026');
  });

  it('devuelve vacío si la fecha no es válida', () => {
    expect(fechaCertificado('no-es-fecha')).toBe('');
    expect(fechaCertificado('')).toBe('');
  });
});

describe('codigoLegible', () => {
  it('agrupa el código de a 4 para leerlo o dictarlo', () => {
    expect(codigoLegible('ABCDEFGH12345678')).toBe('ABCD EFGH 1234 5678');
    expect(codigoLegible('ABCDE')).toBe('ABCD E');
  });

  it('no cambia los caracteres del código, solo los agrupa', () => {
    fc.assert(
      fc.property(fc.stringMatching(/^[A-Z0-9]{16,64}$/), (codigo) => {
        const legible = codigoLegible(codigo);
        return (
          legible.replace(/ /g, '') === codigo && legible.split(' ').every((g) => g.length <= 4)
        );
      }),
      { numRuns: 200 },
    );
  });
});

describe('finalCelular', () => {
  it('toma los últimos 4 dígitos del celular que ya viene enmascarado', () => {
    expect(finalCelular('*********4567')).toBe('4567');
  });

  it('no muestra nada si el valor no viene enmascarado o falta', () => {
    expect(finalCelular('+573001234567')).toBe('');
    expect(finalCelular('3001234567')).toBe('');
    expect(finalCelular(null)).toBe('');
    expect(finalCelular(undefined)).toBe('');
  });

  it('nunca devuelve más de 4 caracteres', () => {
    fc.assert(
      fc.property(fc.string({ maxLength: 20 }), (valor) => finalCelular(valor).length <= 4),
      { numRuns: 200 },
    );
  });
});

describe('mensajeError', () => {
  it('con 409 muestra el mensaje claro del backend (Req 6.2)', () => {
    const detalle = 'Todavía no alcanzas el puntaje mínimo de la evaluación para recibir el certificado.';
    expect(mensajeError(409, detalle)).toBe(detalle);
  });

  it('con 409 sin mensaje usa el genérico', () => {
    expect(mensajeError(409, undefined)).toBe(MENSAJE_GENERICO);
    expect(mensajeError(409, '   ')).toBe(MENSAJE_GENERICO);
  });

  it('con 403 o 404 no revela si el certificado es de otra persona (Req 6.6, 6.7)', () => {
    expect(mensajeError(403, 'No tienes permiso para ver esto.')).toBe(MENSAJE_NO_ENCONTRADO);
    expect(mensajeError(404, 'algo interno')).toBe(MENSAJE_NO_ENCONTRADO);
  });

  it('sin conexión lo dice, y nunca muestra detalles de otros errores', () => {
    expect(mensajeError(0, undefined)).toBe(MENSAJE_SIN_CONEXION);
    expect(mensajeError(500, 'Traceback interno')).toBe(MENSAJE_GENERICO);
    expect(mensajeError(422, 'campo path_id')).toBe(MENSAJE_GENERICO);
  });
});
