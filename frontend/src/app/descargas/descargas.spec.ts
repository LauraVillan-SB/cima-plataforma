import { esCacheDeDatos } from '../core/limpieza-local';
import {
  CACHE_DESCARGAS,
  CLAVE_INDICE,
  CacheDescargas,
  Descarga,
  conDescarga,
  espacioUsado,
  esVideoDescargable,
  formatoMegas,
  guardarIndice,
  leerIndice,
  sinDescarga,
  tamanoDesdeContentRange,
} from './descargas';

/** Caché en memoria: guarda el texto de cada respuesta. */
class CacheFalsa implements CacheDescargas {
  readonly datos = new Map<string, string>();
  async match(clave: string): Promise<{ json(): Promise<unknown> } | undefined> {
    const texto = this.datos.get(clave);
    return texto === undefined ? undefined : { json: async () => JSON.parse(texto) };
  }
  async put(clave: string, respuesta: Response): Promise<void> {
    this.datos.set(clave, await respuesta.text());
  }
  async delete(clave: string): Promise<boolean> {
    return this.datos.delete(clave);
  }
}

function descarga(url: string, fecha: string, bytes = 1024): Descarga {
  return {
    url,
    titulo: 'Video',
    leccion: 'Lección de ejemplo',
    rutaId: 'ruta-1',
    capsulaId: 'capsula-1',
    bytes,
    fecha,
    borrarAlTerminar: false,
  };
}

describe('Descargas de videos (Req 18.1)', () => {
  it.each([
    ['/api/v1/aprendizaje/medios/agro-riesgos.mp4', true],
    ['/api/v1/aprendizaje/medios/tienda-videos.mp4', true],
    ['https://evil.example/api/v1/aprendizaje/medios/x.mp4', false],
    ['/api/v1/aprendizaje/medios/../../secreto.mp4', false],
    ['/api/v1/aprendizaje/medios/video.exe', false],
    ['/api/v1/perfiles/me', false],
  ])('solo descarga videos propios del backend: %s -> %s', (url, esperado) => {
    expect(esVideoDescargable(url)).toBe(esperado);
  });

  it('la caché de descargas NO se vacía al cerrar sesión', () => {
    // La limpieza de core/limpieza-local.ts solo toca las cachés de datos del Service Worker.
    expect(esCacheDeDatos(CACHE_DESCARGAS)).toBe(false);
  });

  it.each([
    ['bytes 0-0/62802733', 62802733],
    ['bytes 0-0/1', 1],
    ['bytes 0-0/*', null],
    ['', null],
    [null, null],
    ['bytes 0-0/0', null],
  ])('lee el tamaño de Content-Range %s', (cabecera, esperado) => {
    expect(tamanoDesdeContentRange(cabecera)).toBe(esperado);
  });

  it.each([
    [62802733, '60 MB'],
    [9542041, '9,1 MB'],
    [524288, '0,5 MB'],
  ])('formatea %d bytes como %s', (bytes, esperado) => {
    expect(formatoMegas(bytes)).toBe(esperado);
  });

  it('guarda y lee el índice, de la descarga más reciente a la más antigua', async () => {
    const cache = new CacheFalsa();
    const vieja = descarga('/api/v1/aprendizaje/medios/a.mp4', '2026-11-01T10:00:00.000Z');
    const nueva = descarga('/api/v1/aprendizaje/medios/b.mp4', '2026-11-10T10:00:00.000Z');
    await guardarIndice(cache, [vieja, nueva]);
    expect((await leerIndice(cache)).map((d) => d.url)).toEqual([nueva.url, vieja.url]);
  });

  it('sin índice devuelve una lista vacía', async () => {
    expect(await leerIndice(new CacheFalsa())).toEqual([]);
  });

  it('descarta entradas manipuladas o mal formadas del índice', async () => {
    const cache = new CacheFalsa();
    const buena = descarga('/api/v1/aprendizaje/medios/a.mp4', '2026-11-01T10:00:00.000Z');
    cache.datos.set(
      CLAVE_INDICE,
      JSON.stringify([
        buena,
        { ...buena, url: 'https://evil.example/x.mp4' },
        { ...buena, bytes: 'mucho' },
        { url: '/api/v1/aprendizaje/medios/c.mp4' },
        null,
      ]),
    );
    expect(await leerIndice(cache)).toEqual([buena]);
  });

  it('un índice dañado se trata como vacío', async () => {
    const cache = new CacheFalsa();
    cache.datos.set(CLAVE_INDICE, '{no es json');
    expect(await leerIndice(cache)).toEqual([]);
  });

  it('agregar reemplaza la misma descarga y quitar la elimina', () => {
    const a = descarga('/api/v1/aprendizaje/medios/a.mp4', '2026-11-01T10:00:00.000Z', 100);
    const b = descarga('/api/v1/aprendizaje/medios/b.mp4', '2026-11-02T10:00:00.000Z', 200);
    const otraVezA = { ...a, bytes: 150 };
    const lista = conDescarga(conDescarga([a], b), otraVezA);
    expect(lista).toHaveLength(2);
    expect(espacioUsado(lista)).toBe(350);
    expect(sinDescarga(lista, a.url).map((d) => d.url)).toEqual([b.url]);
  });
});
