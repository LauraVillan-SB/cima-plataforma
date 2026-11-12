#!/usr/bin/env node
/**
 * Presupuesto de carga de la PWA medido sobre el build real (Tarea 2, Tarea 23.5).
 *
 * Uso, después de `ng build`:  node scripts/presupuesto-carga.cjs [dist/cima-frontend/browser]
 *
 * Por qué no basta con los `budgets` de angular.json: Angular solo mide lo que
 * pasa por su bundler. El Design System (`sb-ui-seguros-bolivar.min.css/js`) se
 * copia como asset y lo carga `index.html`, así que el budget `initial` no lo ve.
 * Este script mide lo que de verdad descarga la página:
 *
 * - Carga inicial (Req 2.3, ≤ 500 kB transferidos): `index.html`, lo que
 *   referencia y las importaciones ESTÁTICAS de cada JS, en cadena. Los `import()`
 *   dinámicos (rutas lazy) no cuentan. El tamaño se estima con gzip nivel 9.
 * - Visita posterior (Req 2.4, ≤ 50 kB de estáticos): con el Service Worker
 *   activo, lo único que se descarga es `ngsw.json` (verificación de versión) más
 *   cualquier recurso inicial que el Service Worker NO tenga en caché.
 * - Peso sin comprimir de la carga inicial frente a 1 MB (Req 10.3): solo aviso,
 *   porque el requisito no precisa si habla de bytes transferidos o sin comprimir.
 *
 * Termina con código 1 si se excede el Req 2.3 o el 2.4. No transmite nada: solo
 * lee archivos locales del build.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const KB = 1000; // kB decimal, como los budgets de Angular.
const LIMITE_INICIAL = 500 * KB; // Req 2.3
const LIMITE_POSTERIOR = 50 * KB; // Req 2.4
const AVISO_SIN_COMPRIMIR = 1000 * KB; // Req 10.3

/** Referencias locales (href/src) de `index.html`. Ignora URLs absolutas y `data:`. */
function recursosDeIndex(html) {
  const refs = new Set();
  const patron = /<(?:link|script)\b[^>]*\b(?:href|src)\s*=\s*["']([^"']+)["']/gi;
  let m;
  while ((m = patron.exec(html)) !== null) {
    const ref = m[1];
    if (/^(?:[a-z]+:)?\/\//i.test(ref) || ref.startsWith('data:') || ref.startsWith('#')) {
      continue;
    }
    refs.add(ref.replace(/^\.?\//, '').split(/[?#]/)[0]);
  }
  return [...refs];
}

/**
 * Importaciones estáticas relativas de un módulo JS (`import ... from "./x.js"`,
 * `import "./x.js"`, `export ... from "./x.js"`). Excluye `import("./x.js")`.
 */
function importacionesEstaticas(js) {
  const refs = new Set();
  const patron = /(?:\bimport|\bexport)\s*(?:[^'"();]*?\bfrom\s*)?["'](\.{1,2}\/[^"']+\.m?js)["']/g;
  let m;
  while ((m = patron.exec(js)) !== null) {
    refs.add(m[1].replace(/^\.\//, ''));
  }
  return [...refs];
}

/** Cierre de la carga inicial: recursos de `index.html` + importaciones estáticas en cadena. */
function cargaInicial(leer, html) {
  const visitados = new Set(['index.html']);
  const pendientes = recursosDeIndex(html);
  while (pendientes.length > 0) {
    const archivo = pendientes.pop();
    if (visitados.has(archivo)) {
      continue;
    }
    const contenido = leer(archivo);
    if (contenido === undefined) {
      continue; // referencia a algo que no está en el build (p. ej. favicon ausente)
    }
    visitados.add(archivo);
    if (/\.m?js$/.test(archivo)) {
      pendientes.push(...importacionesEstaticas(contenido.toString('utf-8')));
    }
  }
  return [...visitados].sort();
}

/** URLs que el Service Worker guarda en caché según `ngsw.json` (todas sus assetGroups). */
function urlsEnCacheDelServiceWorker(ngsw) {
  const urls = new Set();
  for (const grupo of ngsw.assetGroups || []) {
    for (const url of grupo.urls || []) {
      urls.add(url.replace(/^\//, ''));
    }
  }
  return urls;
}

function gzip(buffer) {
  return zlib.gzipSync(buffer, { level: 9 }).length;
}

/** Mide el build. `leer(archivo)` devuelve un Buffer o `undefined` si no existe. */
function medir(leer) {
  const index = leer('index.html');
  if (index === undefined) {
    throw new Error('no se encontró index.html en el build');
  }
  const inicial = cargaInicial(leer, index.toString('utf-8'));
  const detalle = inicial.map((archivo) => {
    const contenido = leer(archivo);
    return { archivo, bruto: contenido.length, gzip: gzip(contenido) };
  });
  const ngswBuffer = leer('ngsw.json');
  const enCache = ngswBuffer ? urlsEnCacheDelServiceWorker(JSON.parse(ngswBuffer.toString('utf-8'))) : new Set();
  const sinCache = detalle.filter((d) => !enCache.has(d.archivo));
  const posterior = (ngswBuffer ? gzip(ngswBuffer) : 0) + sinCache.reduce((t, d) => t + d.gzip, 0);
  return {
    detalle,
    inicialGzip: detalle.reduce((t, d) => t + d.gzip, 0),
    inicialBruto: detalle.reduce((t, d) => t + d.bruto, 0),
    posterior,
    sinCache: sinCache.map((d) => d.archivo),
    conServiceWorker: Boolean(ngswBuffer),
  };
}

function kb(bytes) {
  return `${(bytes / KB).toFixed(1)} kB`;
}

function main(argv) {
  const dist = path.resolve(argv[2] || path.join(__dirname, '..', 'dist', 'cima-frontend', 'browser'));
  const leer = (archivo) => {
    const ruta = path.resolve(dist, archivo);
    // Solo archivos dentro del build (sin path traversal desde index.html o imports).
    if (!ruta.startsWith(dist + path.sep) || !fs.existsSync(ruta) || !fs.statSync(ruta).isFile()) {
      return undefined;
    }
    return fs.readFileSync(ruta);
  };
  const r = medir(leer);

  console.log('Carga inicial (archivo | sin comprimir | gzip):');
  for (const d of r.detalle) {
    console.log(`  ${d.archivo.padEnd(34)} ${kb(d.bruto).padStart(10)} ${kb(d.gzip).padStart(10)}`);
  }
  const fallos = [];
  const linea = (nombre, valor, limite, req) => {
    const ok = valor <= limite;
    console.log(`${ok ? 'OK   ' : 'FALLA'} ${nombre}: ${kb(valor)} (límite ${kb(limite)}, ${req})`);
    if (!ok) fallos.push(req);
  };
  linea('carga inicial transferida (gzip)', r.inicialGzip, LIMITE_INICIAL, 'Req 2.3');
  if (!r.conServiceWorker) {
    console.log('FALLA visita posterior: el build no tiene ngsw.json (Service Worker desactivado)');
    fallos.push('Req 2.4');
  } else {
    linea('visita posterior (ngsw.json + no cacheado)', r.posterior, LIMITE_POSTERIOR, 'Req 2.4');
    if (r.sinCache.length > 0) {
      console.log(`      recursos iniciales sin caché del SW: ${r.sinCache.join(', ')}`);
    }
  }
  const avisoBruto = r.inicialBruto > AVISO_SIN_COMPRIMIR ? 'AVISO' : 'OK   ';
  console.log(`${avisoBruto} carga inicial sin comprimir: ${kb(r.inicialBruto)} (referencia 1 MB, Req 10.3)`);
  return fallos.length === 0 ? 0 : 1;
}

module.exports = {
  recursosDeIndex,
  importacionesEstaticas,
  cargaInicial,
  urlsEnCacheDelServiceWorker,
  medir,
  LIMITE_INICIAL,
  LIMITE_POSTERIOR,
};

if (require.main === module) {
  process.exitCode = main(process.argv);
}
