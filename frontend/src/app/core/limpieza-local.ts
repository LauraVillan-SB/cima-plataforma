/**
 * Limpieza de los datos de la API que el Service Worker guarda en el dispositivo.
 *
 * Lógica pura (sin Angular) para poder probarla con jest.
 *
 * El Service Worker indexa su caché por URL, no por Usuario. En un celular
 * compartido —frecuente entre agricultores y tenderos— lo que dejó en caché la
 * sesión anterior (progreso de la ruta, evaluaciones, historial del chat) quedaría
 * al alcance de quien abra la app después. Por eso se vacía cuando la sesión
 * cambia de manos: al salir, al entrar o registrarse, y cuando la sesión expira.
 *
 * Es una segunda barrera. La primera está en `ngsw-config.json`: solo se cachean
 * por URL explícita los datos que el Req 18.1 pide consultar sin conexión
 * (microcápsulas, rutas, evaluaciones e historial del chat). Nunca la sesión
 * (`/auth/sesion`), el Perfil, los certificados ni los reportes. Los `dataGroups`
 * no admiten patrones negativos, por eso es una allowlist y no `/api/v1/**`.
 *
 * Solo se tocan las cachés de DATOS. Los estáticos del shell (`:assets:`) se
 * conservan, así la siguiente visita no vuelve a descargarlos (Req 2.4).
 */

/** Prefijo de todas las cachés del Service Worker de Angular. */
export const PREFIJO_CACHE_SW = 'ngsw:';

/**
 * Marca de las cachés de `dataGroups` en sus nombres.
 *
 * Verificado en `@angular/service-worker` 22.2.2 (`ngsw-worker.js`): las cachés
 * de datos se llaman `ngsw:<scope>:<versión>:data:<grupo>:cache` y sus tablas
 * `...:data:<grupo>:lru` / `:age`; las de estáticos usan `:assets:`. No es una
 * API pública: si Angular cambiara el formato, esta limpieza dejaría de vaciar
 * datos (la allowlist de `ngsw-config.json` seguiría protegiendo la sesión y el
 * Perfil). Hay una prueba que fija el formato esperado.
 */
export const MARCA_CACHE_DATOS = ':data:';

/** Lo mínimo de `Cache` que se usa: listar y borrar entradas. */
export interface CacheVaciable<R> {
  keys(): Promise<readonly R[]>;
  delete(peticion: R): Promise<boolean>;
}

/** Lo mínimo de `CacheStorage` que se usa. */
export interface AlmacenDeCaches<R> {
  keys(): Promise<string[]>;
  open(nombre: string): Promise<CacheVaciable<R>>;
}

/** Indica si el nombre corresponde a una caché de datos del Service Worker. */
export function esCacheDeDatos(nombre: string): boolean {
  return nombre.startsWith(PREFIJO_CACHE_SW) && nombre.includes(MARCA_CACHE_DATOS);
}

/**
 * Vacía las cachés de datos del Service Worker y devuelve cuántas vació.
 *
 * Borra las ENTRADAS en lugar de borrar la caché con `caches.delete`: el
 * Service Worker en ejecución puede conservar una referencia a la caché abierta
 * y, si solo se borrara el nombre, seguiría sirviendo lo que tenía hasta
 * reiniciarse.
 *
 * Si el navegador no soporta caché (`almacen` indefinido), no hace nada y la
 * app sigue operando (Req 2.5).
 */
export async function vaciarCachesDeDatos<R>(
  almacen: AlmacenDeCaches<R> | undefined,
): Promise<number> {
  if (!almacen) {
    return 0;
  }
  const nombres = (await almacen.keys()).filter(esCacheDeDatos);
  for (const nombre of nombres) {
    const cache = await almacen.open(nombre);
    const peticiones = await cache.keys();
    await Promise.all(peticiones.map((peticion) => cache.delete(peticion)));
  }
  return nombres.length;
}

/** `CacheStorage` del navegador, o indefinido si no existe (Req 2.5). */
export function almacenDelNavegador(): CacheStorage | undefined {
  return typeof caches === 'undefined' ? undefined : caches;
}
