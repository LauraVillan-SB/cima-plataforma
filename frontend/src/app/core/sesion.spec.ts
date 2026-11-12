import * as fc from 'fast-check';

import { RUTA_REFRESCO, debeIntentarRefresco } from './sesion';

/**
 * Pruebas de la regla de renovación de sesión (Req 1.14, 2.6).
 * Feature: cima-plataforma
 */
describe('debeIntentarRefresco', () => {
  it('renueva ante un 403 de la API propia', () => {
    expect(debeIntentarRefresco('/api/v1/perfiles/me', 403, false)).toBe(true);
    expect(debeIntentarRefresco('/api/v1/auth/sesion', 403, false)).toBe(true);
    expect(debeIntentarRefresco('/api/v1/chat/historial?x=1', 403, false)).toBe(true);
  });

  it('no reintenta una petición que ya se reintentó (evita el ciclo)', () => {
    expect(debeIntentarRefresco('/api/v1/perfiles/me', 403, true)).toBe(false);
  });

  it('no actúa en las rutas que gestionan la sesión', () => {
    for (const url of [
      '/api/v1/auth/ingreso',
      '/api/v1/auth/registro',
      RUTA_REFRESCO,
      `${RUTA_REFRESCO}?a=b`,
      '/api/v1/auth/salir',
    ]) {
      expect(debeIntentarRefresco(url, 403, false)).toBe(false);
    }
  });

  it('no actúa fuera de la API propia ni con URLs absolutas', () => {
    expect(debeIntentarRefresco('/assets/icono.svg', 403, false)).toBe(false);
    expect(debeIntentarRefresco('https://otro-sitio.example/api/v1/x', 403, false)).toBe(false);
    expect(debeIntentarRefresco('//otro-sitio.example/api/v1/x', 403, false)).toBe(false);
  });

  it('para todo estado distinto de 403 nunca renueva', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 100, max: 599 }).filter((s) => s !== 403),
        fc.boolean(),
        (estado, reintentada) => {
          expect(debeIntentarRefresco('/api/v1/perfiles/me', estado, reintentada)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
