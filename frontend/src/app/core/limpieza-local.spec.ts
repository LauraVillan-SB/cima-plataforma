import * as fs from 'fs';
import * as path from 'path';

import {
  AlmacenDeCaches,
  CacheVaciable,
  esCacheDeDatos,
  vaciarCachesDeDatos,
} from './limpieza-local';

/**
 * Pruebas de la limpieza de datos locales y de la allowlist del Service Worker.
 *
 * El Service Worker indexa su caché por URL, no por Usuario: en un celular
 * compartido, lo que dejó en caché una sesión quedaría a la vista de la
 * siguiente. Se verifica que (1) `ngsw-config.json` nunca cachea la sesión, el
 * Perfil, los certificados ni los reportes, y sí lo que el Req 18.1 pide sin
 * conexión; y (2) la limpieza vacía solo las cachés de datos y conserva las de
 * estáticos (Req 2.4).
 *
 * Validates: Requirements 2.4, 2.5, 18.1
 */

/** Caché en memoria con entradas `string` (basta para la prueba). */
class CacheFalsa implements CacheVaciable<string> {
  constructor(public entradas: string[]) {}
  async keys(): Promise<readonly string[]> {
    return [...this.entradas];
  }
  async delete(peticion: string): Promise<boolean> {
    const antes = this.entradas.length;
    this.entradas = this.entradas.filter((e) => e !== peticion);
    return this.entradas.length < antes;
  }
}

class AlmacenFalso implements AlmacenDeCaches<string> {
  constructor(public readonly caches: Map<string, CacheFalsa>) {}
  async keys(): Promise<string[]> {
    return [...this.caches.keys()];
  }
  async open(nombre: string): Promise<CacheFalsa> {
    const cache = this.caches.get(nombre);
    if (!cache) {
      throw new Error(`caché inexistente: ${nombre}`);
    }
    return cache;
  }
}

// Nombres con el formato de @angular/service-worker 22.2.2 (ver limpieza-local.ts).
const DATOS = 'ngsw:/:1:data:aprendizaje-offline:cache';
const DATOS_LRU = 'ngsw:/:db:1:data:aprendizaje-offline:lru';
const ESTATICOS = 'ngsw:/:abc123:assets:app:cache';
const CONTROL = 'ngsw:/:db:control';
const AJENA = 'otra-app:data:cache';

describe('Limpieza de datos locales al cambiar la sesión', () => {
  it('reconoce solo las cachés de datos del Service Worker', () => {
    expect(esCacheDeDatos(DATOS)).toBe(true);
    expect(esCacheDeDatos(DATOS_LRU)).toBe(true);
    expect(esCacheDeDatos(ESTATICOS)).toBe(false);
    expect(esCacheDeDatos(CONTROL)).toBe(false);
    expect(esCacheDeDatos(AJENA)).toBe(false);
  });

  it('vacía las cachés de datos y conserva estáticos, control y cachés ajenas', async () => {
    const almacen = new AlmacenFalso(
      new Map([
        [DATOS, new CacheFalsa(['/api/v1/aprendizaje/microcapsulas', '/api/v1/chat/historial'])],
        [DATOS_LRU, new CacheFalsa(['/lru'])],
        [ESTATICOS, new CacheFalsa(['/main.js', '/index.html'])],
        [CONTROL, new CacheFalsa(['/manifests'])],
        [AJENA, new CacheFalsa(['/x'])],
      ]),
    );

    const vaciadas = await vaciarCachesDeDatos(almacen);

    expect(vaciadas).toBe(2);
    expect(almacen.caches.get(DATOS)?.entradas).toEqual([]);
    expect(almacen.caches.get(DATOS_LRU)?.entradas).toEqual([]);
    expect(almacen.caches.get(ESTATICOS)?.entradas).toEqual(['/main.js', '/index.html']);
    expect(almacen.caches.get(CONTROL)?.entradas).toEqual(['/manifests']);
    expect(almacen.caches.get(AJENA)?.entradas).toEqual(['/x']);
    // Se vacían las entradas, no se borra el nombre (el SW puede tener la caché abierta).
    expect([...almacen.caches.keys()]).toContain(DATOS);
  });

  it('sin soporte de caché no falla y la app sigue operando (Req 2.5)', async () => {
    await expect(vaciarCachesDeDatos(undefined)).resolves.toBe(0);
  });
});

// --------------------------------------------------------------------------- //
// Allowlist de ngsw-config.json
// --------------------------------------------------------------------------- //
interface GrupoDeDatos {
  name: string;
  urls: string[];
}

const config = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', '..', '..', 'ngsw-config.json'), 'utf-8'),
) as { dataGroups?: GrupoDeDatos[] };
const grupos = config.dataGroups ?? [];

/**
 * Como el Service Worker de Angular: los patrones de `dataGroups` coinciden de
 * forma parcial (no van anclados). Aquí solo hay rutas literales, sin comodines.
 */
function cubierta(url: string): boolean {
  return grupos.some((g) => g.urls.some((patron) => url.includes(patron)));
}

describe('Allowlist de datos del Service Worker (ngsw-config.json)', () => {
  it('no usa comodines: los dataGroups no admiten patrones negativos', () => {
    for (const grupo of grupos) {
      for (const patron of grupo.urls) {
        expect(patron).not.toMatch(/[*?!]/);
      }
    }
  });

  it.each([
    '/api/v1/auth/sesion',
    '/api/v1/auth/refresco',
    '/api/v1/perfiles/me',
    '/api/v1/certificados/0b6f2a52-0000-4000-8000-000000000000',
    '/api/v1/impacto/tablero',
    '/api/v1/metricas/reportes',
    '/api/v1/encuestas/reportes',
    '/api/v1/chat/mensajes/0b6f2a52-0000-4000-8000-000000000000',
    '/api/v1/gamificacion/reconocimientos',
    '/api/v1/conversion/microseguros/0b6f2a52-0000-4000-8000-000000000000',
  ])('nunca cachea %s', (url) => {
    expect(cubierta(url)).toBe(false);
  });

  it.each([
    '/api/v1/aprendizaje/microcapsulas',
    '/api/v1/aprendizaje/rutas/0b6f2a52-0000-4000-8000-000000000000',
    '/api/v1/evaluaciones/0b6f2a52-0000-4000-8000-000000000000',
    '/api/v1/chat/historial',
  ])('cachea para uso sin conexión %s (Req 18.1, 18.2)', (url) => {
    expect(cubierta(url)).toBe(true);
  });

  it('todo grupo de datos tiene tope de tamaño, de antigüedad y timeout de red', () => {
    const conConfig = config as { dataGroups?: Array<{ cacheConfig: Record<string, unknown> }> };
    for (const grupo of conConfig.dataGroups ?? []) {
      expect(grupo.cacheConfig['maxSize']).toBeGreaterThan(0);
      expect(grupo.cacheConfig['maxAge']).toBeTruthy();
      expect(grupo.cacheConfig['timeout']).toBeTruthy();
    }
  });
});
