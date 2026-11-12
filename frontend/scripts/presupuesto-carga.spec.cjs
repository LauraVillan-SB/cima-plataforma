/**
 * Pruebas del script de presupuesto de carga (Tarea 2, Tarea 23.5; Req 2.3, 2.4).
 *
 * Usan un build en memoria: no hace falta correr `ng build` para probar cómo se
 * arma la carga inicial ni cómo se calcula la visita posterior.
 */
'use strict';

const {
  recursosDeIndex,
  importacionesEstaticas,
  cargaInicial,
  medir,
} = require('./presupuesto-carga.cjs');

/** Build simulado: nombre de archivo -> contenido. */
function lectorDe(archivos) {
  return (nombre) => (nombre in archivos ? Buffer.from(archivos[nombre]) : undefined);
}

const INDEX = `<!doctype html><html><head>
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="icon" href="favicon.ico">
  <link rel="stylesheet" href="sb-ui.min.css" data-beasties-skip>
  <link rel="preconnect" href="https://fonts.example.com">
  <script type="module" src="sb-ui.min.js"></script>
</head><body>
  <script src="polyfills.js" type="module"></script><script src="main.js" type="module"></script>
</body></html>`;

describe('recursosDeIndex', () => {
  it('toma las referencias locales e ignora las absolutas', () => {
    expect(recursosDeIndex(INDEX).sort()).toEqual(
      ['favicon.ico', 'main.js', 'manifest.webmanifest', 'polyfills.js', 'sb-ui.min.css', 'sb-ui.min.js'].sort(),
    );
  });
});

describe('importacionesEstaticas', () => {
  it('incluye import/export estáticos y excluye import() dinámico', () => {
    const js =
      'import{a as b}from"./chunk-A.js";import"./chunk-B.js";export{c}from"./chunk-C.js";' +
      'const r=()=>import("./chunk-LAZY.js");';
    expect(importacionesEstaticas(js).sort()).toEqual(['chunk-A.js', 'chunk-B.js', 'chunk-C.js']);
  });
});

describe('cargaInicial', () => {
  it('sigue las importaciones estáticas en cadena y omite lo lazy y lo ausente', () => {
    const leer = lectorDe({
      'index.html': INDEX,
      'manifest.webmanifest': '{}',
      'sb-ui.min.css': 'body{}',
      'sb-ui.min.js': 'export{}',
      'polyfills.js': '',
      'main.js': 'import"./chunk-A.js";const l=()=>import("./chunk-LAZY.js");',
      'chunk-A.js': 'import"./chunk-B.js";',
      'chunk-B.js': '',
      'chunk-LAZY.js': '',
    });
    expect(cargaInicial(leer, INDEX)).toEqual(
      [
        'chunk-A.js',
        'chunk-B.js',
        'index.html',
        'main.js',
        'manifest.webmanifest',
        'polyfills.js',
        'sb-ui.min.css',
        'sb-ui.min.js',
      ].sort(),
    );
  });
});

describe('medir', () => {
  const base = {
    'index.html': INDEX,
    'manifest.webmanifest': '{}',
    'sb-ui.min.css': 'body{}'.repeat(100),
    'sb-ui.min.js': 'export{}',
    'polyfills.js': '',
    'main.js': '',
  };

  it('con todo en caché del Service Worker, la visita posterior solo baja ngsw.json', () => {
    const ngsw = {
      assetGroups: [
        {
          urls: ['/index.html', '/manifest.webmanifest', '/sb-ui.min.css', '/sb-ui.min.js', '/polyfills.js', '/main.js'],
        },
      ],
    };
    const r = medir(lectorDe({ ...base, 'ngsw.json': JSON.stringify(ngsw) }));
    expect(r.conServiceWorker).toBe(true);
    expect(r.sinCache).toEqual([]);
    expect(r.posterior).toBeLessThan(r.inicialGzip);
  });

  it('un recurso inicial fuera del Service Worker cuenta en la visita posterior', () => {
    const ngsw = { assetGroups: [{ urls: ['/index.html', '/main.js'] }] };
    const r = medir(lectorDe({ ...base, 'ngsw.json': JSON.stringify(ngsw) }));
    expect(r.sinCache).toEqual(expect.arrayContaining(['sb-ui.min.css', 'sb-ui.min.js']));
  });

  it('sin ngsw.json se informa que no hay Service Worker', () => {
    expect(medir(lectorDe(base)).conServiceWorker).toBe(false);
  });

  it('sin index.html falla con un error claro', () => {
    expect(() => medir(lectorDe({}))).toThrow('index.html');
  });
});
