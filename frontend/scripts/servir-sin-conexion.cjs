#!/usr/bin/env node
/**
 * Sirve la app compilada en http://localhost:4300 para probar el modo sin conexión.
 *
 * `ng serve` no activa el Service Worker; solo la app compilada lo hace. Este
 * servidor entrega `dist/cima-frontend/browser` y reenvía `/api/*` al backend
 * local (http://127.0.0.1:8000), igual que el proxy de desarrollo, para que la
 * cookie de sesión siga siendo del mismo origen. Solo para pruebas locales:
 * escucha en 127.0.0.1 y no usa dependencias externas.
 *
 * Uso: npm run sin-conexion   (compila y sirve)
 *      node scripts/servir-sin-conexion.cjs   (sirve lo ya compilado)
 */
'use strict';

const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const PUERTO = Number(process.env.PUERTO_SIN_CONEXION || 4300);
const BACKEND = { host: '127.0.0.1', port: 8000 };
const RAIZ = path.resolve(__dirname, '..', 'dist', 'cima-frontend', 'browser');

const TIPOS = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
};

/** Reenvía la petición al backend fijo, tal cual (método, cabeceras y cuerpo, incluido Range). */
function reenviar(req, res) {
  const salida = http.request(
    { ...BACKEND, method: req.method, path: req.url, headers: { ...req.headers, host: `${BACKEND.host}:${BACKEND.port}` } },
    (respuesta) => {
      res.writeHead(respuesta.statusCode || 502, respuesta.headers);
      respuesta.pipe(res);
    },
  );
  salida.on('error', () => {
    if (!res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
    }
    res.end(JSON.stringify({ detail: 'El backend local no responde.' }));
  });
  req.pipe(salida);
}

/** Resuelve un archivo dentro de RAIZ; devuelve null si la dirección es inválida o sale de la carpeta. */
function resolverArchivo(urlPath) {
  let relativo;
  try {
    relativo = decodeURIComponent(urlPath.split('?')[0]);
  } catch (error) {
    if (error instanceof URIError) {
      return null;
    }
    throw error;
  }
  const completo = path.resolve(RAIZ, '.' + relativo);
  return completo === RAIZ || completo.startsWith(RAIZ + path.sep) ? completo : null;
}

function servirEstatico(req, res) {
  const archivo = resolverArchivo(req.url || '/');
  if (!archivo) {
    res.writeHead(400).end();
    return;
  }
  const existe = fs.existsSync(archivo) && fs.statSync(archivo).isFile();
  // Rutas de la app (sin extensión) se resuelven con index.html; el Service Worker hace lo mismo.
  const destino = existe ? archivo : path.join(RAIZ, 'index.html');
  const tipo = TIPOS[path.extname(destino)] || 'application/octet-stream';
  // El Service Worker y su índice nunca se cachean en el navegador, para que se actualicen.
  const sinCache = /(?:ngsw-worker\.js|ngsw\.json|index\.html)$/.test(destino);
  res.writeHead(200, { 'Content-Type': tipo, 'Cache-Control': sinCache ? 'no-cache' : 'public, max-age=3600' });
  fs.createReadStream(destino).pipe(res);
}

if (!fs.existsSync(path.join(RAIZ, 'index.html'))) {
  console.error(`No encuentro la app compilada en ${RAIZ}. Ejecuta primero: npm run build`);
  process.exit(1);
}

http
  .createServer((req, res) => {
    if ((req.url || '').startsWith('/api/')) {
      reenviar(req, res);
    } else {
      servirEstatico(req, res);
    }
  })
  .listen(PUERTO, '127.0.0.1', () => {
    console.log(`CIMA compilada en http://localhost:${PUERTO} (API -> http://${BACKEND.host}:${BACKEND.port})`);
    console.log('Para probar sin conexión: DevTools > Network > "Offline", o DevTools > Application > Service Workers > "Offline".');
  });
