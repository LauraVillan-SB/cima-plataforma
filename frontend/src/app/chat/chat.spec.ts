import * as fc from 'fast-check';

import {
  TEXTO_MAX,
  TIEMPO_MAXIMO_SEGUNDOS,
  duracionVozValida,
  elegirMimeAudio,
  esEstadoFinal,
  extensionDeMime,
  faseDeChat,
  textoValido,
} from './chat';

/**
 * Pruebas de la lógica pura del chat (Tarea 23.2, Req 3.2, 3.4, 3.7, 3.8).
 * Feature: cima-plataforma
 */
describe('faseDeChat', () => {
  const pendientes = ['encolado', 'procesando'];

  it('muestra "esperando" antes del umbral de 15 s', () => {
    for (const estado of pendientes) {
      expect(faseDeChat(estado, 0, 15)).toBe('esperando');
      expect(faseDeChat(estado, 14.9, 15)).toBe('esperando');
    }
  });

  it('muestra el indicador de espera desde los 15 s y hasta antes de los 60 s', () => {
    for (const estado of pendientes) {
      expect(faseDeChat(estado, 15, 15)).toBe('procesando_lento');
      expect(faseDeChat(estado, 59.9, 15)).toBe('procesando_lento');
    }
  });

  it('da la espera por agotada a los 60 s', () => {
    for (const estado of pendientes) {
      expect(faseDeChat(estado, TIEMPO_MAXIMO_SEGUNDOS, 15)).toBe('tiempo_agotado');
      expect(faseDeChat(estado, 300, 15)).toBe('tiempo_agotado');
    }
  });

  it('los estados finales mandan sobre el tiempo transcurrido', () => {
    fc.assert(
      fc.property(fc.double({ min: 0, max: 1000, noNaN: true }), (segundos) => {
        expect(faseDeChat('listo', segundos, 15)).toBe('listo');
        expect(faseDeChat('error', segundos, 15)).toBe('error');
        expect(faseDeChat('repetir_voz', segundos, 15)).toBe('repetir_voz');
      }),
      { numRuns: 100 },
    );
  });

  it('un estado desconocido se trata como en curso', () => {
    expect(faseDeChat('otro_estado', 1, 15)).toBe('esperando');
    expect(esEstadoFinal('otro_estado')).toBe(false);
  });

  it('solo listo, error y repetir_voz son finales', () => {
    expect(esEstadoFinal('listo')).toBe(true);
    expect(esEstadoFinal('error')).toBe(true);
    expect(esEstadoFinal('repetir_voz')).toBe(true);
    expect(esEstadoFinal('encolado')).toBe(false);
    expect(esEstadoFinal('procesando')).toBe(false);
  });
});

describe('textoValido', () => {
  it('rechaza vacío o solo espacios', () => {
    expect(textoValido('')).toBe(false);
    expect(textoValido('    ')).toBe(false);
  });

  it('acepta entre 1 y 2000 caracteres tras recortar', () => {
    expect(textoValido('a')).toBe(true);
    expect(textoValido('a'.repeat(TEXTO_MAX))).toBe(true);
    expect(textoValido(`  ${'a'.repeat(TEXTO_MAX)}  `)).toBe(true);
  });

  it('rechaza más de 2000 caracteres', () => {
    expect(textoValido('a'.repeat(TEXTO_MAX + 1))).toBe(false);
  });
});

describe('duracionVozValida', () => {
  it('acepta de 1 a 120 s, extremos incluidos', () => {
    expect(duracionVozValida(1)).toBe(true);
    expect(duracionVozValida(120)).toBe(true);
    expect(duracionVozValida(45.5)).toBe(true);
  });

  it('rechaza fuera de rango y valores no finitos', () => {
    expect(duracionVozValida(0.99)).toBe(false);
    expect(duracionVozValida(120.01)).toBe(false);
    expect(duracionVozValida(Number.NaN)).toBe(false);
    expect(duracionVozValida(Number.POSITIVE_INFINITY)).toBe(false);
  });
});

describe('formato de audio', () => {
  it('elige el primer formato soportado por el navegador', () => {
    expect(elegirMimeAudio((m) => m === 'audio/ogg')).toBe('audio/ogg');
    expect(elegirMimeAudio(() => true)).toBe('audio/mp4');
  });

  it('devuelve null si el navegador solo graba formatos que el servidor rechaza', () => {
    expect(elegirMimeAudio((m) => m.includes('webm'))).toBeNull();
    expect(elegirMimeAudio(() => false)).toBeNull();
  });

  it('asigna una extensión coherente con el formato', () => {
    expect(extensionDeMime('audio/mp4')).toBe('m4a');
    expect(extensionDeMime('audio/ogg;codecs=opus')).toBe('ogg');
    expect(extensionDeMime('audio/mpeg')).toBe('mp3');
  });
});
