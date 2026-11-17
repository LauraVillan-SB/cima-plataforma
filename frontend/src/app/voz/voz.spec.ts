import * as fc from 'fast-check';

import {
  INTERVALO_MEDICION_MS,
  SEGUNDOS_MINIMOS_CON_VOZ,
  UMBRAL_NIVEL_VOZ,
  elegirVoz,
  hayVozSuficiente,
  medicionConfiable,
  nivelRms,
  textoParaLeer,
} from './voz';

/**
 * Pruebas de la lógica pura de voz (Tarea 11.4, Req 14.3, 14.5).
 * Feature: cima-plataforma
 */
describe('nivelRms', () => {
  it('da 0 con silencio o sin muestras', () => {
    expect(nivelRms(new Float32Array(2048))).toBe(0);
    expect(nivelRms([])).toBe(0);
  });

  it('da la amplitud de una señal constante', () => {
    expect(nivelRms([0.5, -0.5, 0.5, -0.5])).toBeCloseTo(0.5);
  });

  it('descarta un bloque con valores no finitos', () => {
    expect(nivelRms([0.1, Number.NaN, 0.2])).toBe(0);
  });

  it('siempre queda entre 0 y 1 con muestras en [-1, 1]', () => {
    fc.assert(
      fc.property(fc.array(fc.double({ min: -1, max: 1, noNaN: true }), { minLength: 1 }), (muestras) => {
        const nivel = nivelRms(muestras);
        return nivel >= 0 && nivel <= 1 + 1e-9;
      }),
      { numRuns: 200 },
    );
  });
});

describe('hayVozSuficiente', () => {
  const medicionesMinimas = Math.ceil((SEGUNDOS_MINIMOS_CON_VOZ * 1000) / INTERVALO_MEDICION_MS);

  it('rechaza una nota en silencio o con ruido de fondo bajo', () => {
    expect(hayVozSuficiente(new Array(50).fill(0))).toBe(false);
    expect(hayVozSuficiente(new Array(50).fill(UMBRAL_NIVEL_VOZ / 2))).toBe(false);
  });

  it('acepta desde el mínimo de mediciones con voz', () => {
    const conVoz = new Array(medicionesMinimas).fill(0.1);
    expect(hayVozSuficiente([...new Array(30).fill(0), ...conVoz])).toBe(true);
    expect(hayVozSuficiente([...new Array(30).fill(0), ...conVoz.slice(1)])).toBe(false);
  });

  it('no cuenta valores no finitos como voz', () => {
    expect(hayVozSuficiente(new Array(50).fill(Number.NaN))).toBe(false);
  });

  it('es verdadero si y solo si hay suficientes mediciones sobre el umbral', () => {
    fc.assert(
      fc.property(fc.array(fc.double({ min: 0, max: 1, noNaN: true }), { maxLength: 200 }), (niveles) => {
        const conVoz = niveles.filter((n) => n >= UMBRAL_NIVEL_VOZ).length;
        return hayVozSuficiente(niveles) === conVoz >= medicionesMinimas;
      }),
      { numRuns: 200 },
    );
  });
});

describe('medicionConfiable', () => {
  it('con el contexto corriendo, todo en cero cuenta como silencio y bloquea el envío', () => {
    const ceros = new Array(50).fill(0);
    expect(medicionConfiable(true, ceros)).toBe(true);
    expect(medicionConfiable(true, ceros) && !hayVozSuficiente(ceros)).toBe(true);
  });

  it('con el contexto suspendido no se confía en la medición', () => {
    expect(medicionConfiable(false, new Array(50).fill(0))).toBe(false);
    expect(medicionConfiable(false, new Array(50).fill(0.2))).toBe(false);
  });

  it('sin mediciones no se confía en ella', () => {
    expect(medicionConfiable(true, [])).toBe(false);
  });
});

describe('elegirVoz', () => {
  it('prefiere el español de Colombia', () => {
    const voces = [{ lang: 'en-US' }, { lang: 'es-ES' }, { lang: 'es-MX' }, { lang: 'es-CO' }];
    expect(elegirVoz(voces)?.lang).toBe('es-CO');
  });

  it('luego una variante latinoamericana antes que la de España', () => {
    expect(elegirVoz([{ lang: 'es-ES' }, { lang: 'es-US' }])?.lang).toBe('es-US');
    expect(elegirVoz([{ lang: 'es_MX' }, { lang: 'es-ES' }])?.lang).toBe('es_MX');
  });

  it('acepta cualquier español si no hay otra', () => {
    expect(elegirVoz([{ lang: 'en-GB' }, { lang: 'es-ES' }])?.lang).toBe('es-ES');
  });

  it('devuelve null si no hay voces en español', () => {
    expect(elegirVoz([{ lang: 'en-US' }, { lang: 'pt-BR' }])).toBeNull();
    expect(elegirVoz([])).toBeNull();
  });
});

describe('textoParaLeer', () => {
  it('quita los emojis, los signos de formato y la etiqueta de IA del inicio', () => {
    expect(textoParaLeer('🤖 Asistente de CIMA (IA): Guarda **una parte** de la venta. 👍')).toBe(
      'Guarda una parte de la venta.',
    );
  });

  it('solo salta la etiqueta al inicio, no si aparece dentro de la respuesta', () => {
    expect(textoParaLeer('Hola. Asistente de CIMA (IA): es mi nombre.')).toBe(
      'Hola. Asistente de CIMA (IA): es mi nombre.',
    );
  });

  it('une saltos de línea y espacios de más', () => {
    expect(textoParaLeer('Primero esto.\n\nLuego   aquello.')).toBe('Primero esto. Luego aquello.');
  });

  it('conserva letras con tilde, eñes y signos de pregunta', () => {
    expect(textoParaLeer('¿Cómo cuidas el café en la montaña?')).toBe(
      '¿Cómo cuidas el café en la montaña?',
    );
  });

  it('nunca deja emojis, asteriscos ni espacios dobles', () => {
    fc.assert(
      fc.property(fc.string({ unit: 'grapheme', maxLength: 200 }), (texto) => {
        const limpio = textoParaLeer(texto);
        return (
          !/\p{Extended_Pictographic}/u.test(limpio) &&
          !limpio.includes('*') &&
          !/\s{2}/.test(limpio) &&
          limpio === limpio.trim()
        );
      }),
      { numRuns: 200 },
    );
  });
});
