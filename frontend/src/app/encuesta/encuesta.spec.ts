import * as fc from 'fast-check';

import {
  COMENTARIO_MAX,
  MENSAJE_GENERICO,
  MENSAJE_SIN_CONEXION,
  MENSAJE_SIN_ENCUESTA,
  OPCIONES_CALIFICACION,
  armarRespuesta,
  calificacionValida,
  mensajeError,
  preguntaDeTipo,
} from './encuesta';

/**
 * Pruebas de la lógica pura de la Encuesta de Satisfacción (Req 20.1–20.7).
 * Feature: cima-plataforma
 */
const PERFIL = { id: '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b', geo_zone: 'Huila' };
const EVENTO = '0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';

describe('opciones y validación de la calificación', () => {
  it('ofrece exactamente la escala de 1 a 5', () => {
    expect(OPCIONES_CALIFICACION.map((o) => o.valor)).toEqual([1, 2, 3, 4, 5]);
    expect(OPCIONES_CALIFICACION.every((o) => o.etiqueta.length > 0)).toBe(true);
  });

  it('solo acepta enteros de 1 a 5', () => {
    fc.assert(
      fc.property(fc.integer({ min: -20, max: 20 }), (n) => calificacionValida(n) === (n >= 1 && n <= 5)),
      { numRuns: 200 },
    );
    expect(calificacionValida(null)).toBe(false);
    expect(calificacionValida(2.5)).toBe(false);
  });
});

describe('preguntaDeTipo', () => {
  const preguntas = [
    { id: 'calificacion', text: '¿Qué tanto te sirvió?', type: 'rating' },
    { id: 'comentario', text: 'Cuéntanos', type: 'text' },
  ];

  it('encuentra la calificación y el comentario', () => {
    expect(preguntaDeTipo(preguntas, 'rating')?.id).toBe('calificacion');
    expect(preguntaDeTipo(preguntas, 'text')?.id).toBe('comentario');
  });

  it('devuelve null si la encuesta no trae ese tipo', () => {
    expect(preguntaDeTipo([preguntas[0]], 'text')).toBeNull();
  });
});

describe('armarRespuesta', () => {
  it('arma el cuerpo con el comentario recortado y la zona', () => {
    expect(armarRespuesta(EVENTO, PERFIL, 4, '  Me sirvió mucho  ')).toEqual({
      client_event_id: EVENTO,
      profile_id: PERFIL.id,
      rating: 4,
      answers: { comentario: 'Me sirvió mucho' },
      geo_zone: 'Huila',
    });
  });

  it('sin comentario ni zona no manda esos campos', () => {
    const cuerpo = armarRespuesta(EVENTO, { id: PERFIL.id, geo_zone: '' }, 5, '   ');
    expect(cuerpo.answers).toEqual({});
    expect('geo_zone' in cuerpo).toBe(false);
  });

  it('nunca manda un comentario más largo que el máximo', () => {
    fc.assert(
      fc.property(fc.string({ maxLength: COMENTARIO_MAX * 2 }), (texto) => {
        const cuerpo = armarRespuesta(EVENTO, PERFIL, 3, texto);
        return (cuerpo.answers.comentario ?? '').length <= COMENTARIO_MAX;
      }),
      { numRuns: 200 },
    );
  });
});

describe('mensajeError', () => {
  it('con 409 y 422 de texto muestra el mensaje claro del backend', () => {
    expect(mensajeError(409, 'Ya nos diste tu opinión sobre esta ruta. ¡Gracias!')).toBe(
      'Ya nos diste tu opinión sobre esta ruta. ¡Gracias!',
    );
    expect(mensajeError(422, 'Tu comentario parece tener datos personales.')).toBe(
      'Tu comentario parece tener datos personales.',
    );
  });

  it('un 422 de validación (arreglo) usa el mensaje propio', () => {
    expect(mensajeError(422, [{ loc: ['body', 'rating'] }])).toBe(MENSAJE_GENERICO);
  });

  it('sin encuesta, sin conexión y otros errores usan mensajes propios', () => {
    expect(mensajeError(404, 'algo interno')).toBe(MENSAJE_SIN_ENCUESTA);
    expect(mensajeError(0, undefined)).toBe(MENSAJE_SIN_CONEXION);
    expect(mensajeError(500, 'Traceback')).toBe(MENSAJE_GENERICO);
  });
});
