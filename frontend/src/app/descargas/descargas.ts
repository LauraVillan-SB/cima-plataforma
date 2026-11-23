/**
 * Descargas de videos propios para verlos sin conexión (Req 18.1).
 *
 * Lógica pura (sin Angular) para poder probarla con jest; el servicio
 * `DescargasService` la usa con la `CacheStorage` real del navegador.
 *
 * Los videos se guardan en una caché propia (`CACHE_DESCARGAS`), separada de las
 * del Service Worker de Angular, por dos razones:
 * - El Service Worker no sirve bien peticiones por rango, que es como el
 *   navegador reproduce un video; aquí el video se lee completo de la caché y se
 *   reproduce desde una URL local (`blob:`).
 * - Las descargas son de la persona y NO se borran al cerrar sesión: la limpieza
 *   de `core/limpieza-local.ts` solo vacía las cachés `ngsw:...:data:`. Los videos
 *   son material educativo público, sin datos personales; el índice guarda solo el
 *   título de la cápsula, el tamaño y la fecha.
 */

/** Nombre de la caché de descargas. Cambiar la versión invalida lo guardado. */
export const CACHE_DESCARGAS = 'cima-descargas-v1';

/** Clave interna del índice de descargas dentro de la misma caché. */
export const CLAVE_INDICE = '/cima-descargas/indice.json';

/**
 * Solo se descargan videos propios del backend: relativos y con el prefijo fijo,
 * igual al patrón que valida la lección y el servidor.
 */
export const PATRON_VIDEO_PROPIO = /^\/api\/v1\/aprendizaje\/medios\/[a-z0-9][a-z0-9-]{0,62}\.mp4$/;

/** Una descarga guardada en el dispositivo. */
export interface Descarga {
  /** Dirección del video en el backend; es la clave en la caché. */
  readonly url: string;
  /** Título del video, para mostrarlo en "Mis descargas". */
  readonly titulo: string;
  /** Título de la lección a la que pertenece. */
  readonly leccion: string;
  /** Ruta y cápsula, para volver a la lección cuando haya conexión. */
  readonly rutaId: string;
  readonly capsulaId: string;
  /** Tamaño en bytes. */
  readonly bytes: number;
  /** Fecha de descarga en ISO-8601. */
  readonly fecha: string;
  /** Si es `true`, se borra apenas el video se termine de ver. */
  readonly borrarAlTerminar: boolean;
}

/** Lo mínimo de `Cache` que se usa. */
export interface CacheDescargas {
  match(clave: string): Promise<{ json(): Promise<unknown> } | undefined>;
  put(clave: string, respuesta: Response): Promise<void>;
  delete(clave: string): Promise<boolean>;
}

/** Indica si una dirección puede descargarse. */
export function esVideoDescargable(url: string): boolean {
  return PATRON_VIDEO_PROPIO.test(url);
}

/**
 * Lee el tamaño total de una respuesta parcial (`Content-Range: bytes 0-0/12345`).
 * @param contentRange valor de la cabecera, o `null`
 * @returns el total en bytes, o `null` si no viene o no es válido
 */
export function tamanoDesdeContentRange(contentRange: string | null): number | null {
  const m = /^bytes \d+-\d+\/(\d+)$/.exec((contentRange ?? '').trim());
  if (!m) {
    return null;
  }
  const total = Number(m[1]);
  return Number.isSafeInteger(total) && total > 0 ? total : null;
}

/**
 * Formatea bytes en megas para la persona ("42 MB", "0,5 MB").
 * @param bytes tamaño en bytes
 * @returns texto corto en español
 */
export function formatoMegas(bytes: number): string {
  const megas = bytes / (1024 * 1024);
  const texto = megas >= 10 ? Math.round(megas).toString() : megas.toFixed(1).replace('.', ',');
  return `${texto} MB`;
}

/** Valida una entrada del índice leída del dispositivo (Zero Trust). */
function esDescarga(valor: unknown): valor is Descarga {
  if (typeof valor !== 'object' || valor === null) {
    return false;
  }
  const d = valor as Record<string, unknown>;
  return (
    typeof d['url'] === 'string' &&
    esVideoDescargable(d['url']) &&
    typeof d['titulo'] === 'string' &&
    typeof d['leccion'] === 'string' &&
    typeof d['rutaId'] === 'string' &&
    typeof d['capsulaId'] === 'string' &&
    typeof d['bytes'] === 'number' &&
    d['bytes'] >= 0 &&
    typeof d['fecha'] === 'string' &&
    typeof d['borrarAlTerminar'] === 'boolean'
  );
}

/**
 * Lee el índice de descargas. Descarta entradas mal formadas o con direcciones
 * que no son videos propios, por si el almacenamiento fue manipulado.
 */
export async function leerIndice(cache: CacheDescargas): Promise<Descarga[]> {
  const respuesta = await cache.match(CLAVE_INDICE);
  if (!respuesta) {
    return [];
  }
  let datos: unknown;
  try {
    datos = await respuesta.json();
  } catch {
    // Índice dañado: se trata como vacío; los videos se pueden volver a descargar.
    return [];
  }
  return Array.isArray(datos) ? datos.filter(esDescarga) : [];
}

/** Guarda el índice de descargas, ordenado de la más reciente a la más antigua. */
export async function guardarIndice(cache: CacheDescargas, descargas: readonly Descarga[]): Promise<void> {
  const ordenadas = [...descargas].sort((a, b) => b.fecha.localeCompare(a.fecha));
  await cache.put(
    CLAVE_INDICE,
    new Response(JSON.stringify(ordenadas), { headers: { 'Content-Type': 'application/json' } }),
  );
}

/** Agrega o reemplaza una descarga en el índice. */
export function conDescarga(descargas: readonly Descarga[], nueva: Descarga): Descarga[] {
  return [nueva, ...descargas.filter((d) => d.url !== nueva.url)];
}

/** Quita una descarga del índice. */
export function sinDescarga(descargas: readonly Descarga[], url: string): Descarga[] {
  return descargas.filter((d) => d.url !== url);
}

/** Suma el espacio que ocupan las descargas, en bytes. */
export function espacioUsado(descargas: readonly Descarga[]): number {
  return descargas.reduce((total, d) => total + d.bytes, 0);
}
