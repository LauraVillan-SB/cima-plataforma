import { Injectable, computed, signal } from '@angular/core';

import {
  CACHE_DESCARGAS,
  Descarga,
  conDescarga,
  esVideoDescargable,
  espacioUsado,
  guardarIndice,
  leerIndice,
  sinDescarga,
  tamanoDesdeContentRange,
} from './descargas';

/** Motivo por el que una descarga no se pudo hacer, para mostrar un mensaje simple. */
export type MotivoFalla = 'sin_soporte' | 'no_permitido' | 'espacio' | 'red';

/** Falla de una descarga con un motivo conocido (nunca se muestra el detalle técnico). */
export class ErrorDescarga extends Error {
  constructor(readonly motivo: MotivoFalla) {
    super(motivo);
    this.name = 'ErrorDescarga';
  }
}

/** Datos de la lección que acompañan a una descarga. */
export interface DatosDescarga {
  readonly url: string;
  readonly titulo: string;
  readonly leccion: string;
  readonly rutaId: string;
  readonly capsulaId: string;
}

/** `fetch` lanza `TypeError` cuando no hay red; cualquier otro error es un fallo real. */
function esFallaDeRed(error: unknown): boolean {
  return error instanceof TypeError;
}

/** El navegador lanza `QuotaExceededError` cuando no queda espacio para guardar. */
function esFaltaDeEspacio(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'QuotaExceededError';
}

/**
 * Descarga videos propios al dispositivo para verlos sin conexión (Req 18.1).
 *
 * Usa una caché propia del navegador (ver `descargas.ts`), que no se borra al
 * cerrar sesión: la persona decide qué borrar desde "Mis descargas" o pide que se
 * borre al terminar de ver el video. El video se pide al backend con la sesión;
 * después se reproduce desde el dispositivo, sin volver a gastar datos.
 */
@Injectable({ providedIn: 'root' })
export class DescargasService {
  /** `false` si el navegador no permite guardar archivos (Req 2.5). */
  readonly disponible = typeof caches !== 'undefined';

  /** Descargas guardadas, de la más reciente a la más antigua. */
  readonly lista = signal<readonly Descarga[]>([]);

  /** Avance de las descargas en curso, de 0 a 1, por dirección del video. */
  readonly progreso = signal<ReadonlyMap<string, number>>(new Map());

  /** Espacio que ocupan las descargas, en bytes. */
  readonly bytesUsados = computed(() => espacioUsado(this.lista()));

  private readonly listo: Promise<void>;

  constructor() {
    this.listo = this.recargar();
  }

  /** Vuelve a leer el índice del dispositivo. */
  async recargar(): Promise<void> {
    if (!this.disponible) {
      return;
    }
    this.lista.set(await leerIndice(await caches.open(CACHE_DESCARGAS)));
  }

  /** Indica si el video ya está guardado en el dispositivo. */
  estaDescargado(url: string): boolean {
    return this.lista().some((d) => d.url === url);
  }

  /** Devuelve la descarga del video, si existe. */
  buscar(url: string): Descarga | undefined {
    return this.lista().find((d) => d.url === url);
  }

  /**
   * Consulta el tamaño del video sin bajarlo: pide solo el primer byte y lee el
   * total de `Content-Range`. Devuelve `null` si no se puede saber.
   */
  async tamano(url: string): Promise<number | null> {
    if (!esVideoDescargable(url)) {
      return null;
    }
    let respuesta: Response;
    try {
      respuesta = await fetch(url, { headers: { Range: 'bytes=0-0' }, credentials: 'same-origin' });
    } catch (error) {
      if (esFallaDeRed(error)) {
        // Sin conexión: el botón se muestra sin el tamaño.
        return null;
      }
      throw error;
    }
    void respuesta.body?.cancel();
    return respuesta.status === 206 ? tamanoDesdeContentRange(respuesta.headers.get('Content-Range')) : null;
  }

  /**
   * Descarga el video y lo guarda en el dispositivo, informando el avance.
   * @throws ErrorDescarga con el motivo si no se pudo guardar
   */
  async descargar(datos: DatosDescarga, borrarAlTerminar: boolean): Promise<void> {
    if (!this.disponible) {
      throw new ErrorDescarga('sin_soporte');
    }
    if (!esVideoDescargable(datos.url)) {
      throw new ErrorDescarga('no_permitido');
    }
    await this.listo;
    // Pide al navegador no borrar las descargas por falta de espacio (si lo permite).
    void navigator.storage?.persist?.();
    const cache = await caches.open(CACHE_DESCARGAS);
    let bytes = 0;
    this.marcarProgreso(datos.url, 0);
    try {
      const respuesta = await fetch(datos.url, { credentials: 'same-origin', cache: 'no-store' });
      if (!respuesta.ok || !respuesta.body) {
        throw new ErrorDescarga('red');
      }
      const total = Number(respuesta.headers.get('Content-Length')) || 0;
      const contador = new TransformStream<Uint8Array, Uint8Array>({
        transform: (trozo, control) => {
          bytes += trozo.byteLength;
          if (total > 0) {
            this.marcarProgreso(datos.url, Math.min(1, bytes / total));
          }
          control.enqueue(trozo);
        },
      });
      // Se guarda mientras llega, sin cargar todo el video en memoria.
      await cache.put(
        datos.url,
        new Response(respuesta.body.pipeThrough(contador), { headers: { 'Content-Type': 'video/mp4' } }),
      );
    } catch (error) {
      // No se deja un video a medias en el dispositivo.
      await cache.delete(datos.url);
      if (error instanceof ErrorDescarga) {
        throw error;
      }
      if (esFaltaDeEspacio(error)) {
        throw new ErrorDescarga('espacio');
      }
      if (esFallaDeRed(error)) {
        throw new ErrorDescarga('red');
      }
      throw error;
    } finally {
      this.quitarProgreso(datos.url);
    }
    const nueva: Descarga = { ...datos, bytes, fecha: new Date().toISOString(), borrarAlTerminar };
    await this.guardar(conDescarga(this.lista(), nueva));
  }

  /**
   * Devuelve una dirección local (`blob:`) para reproducir el video guardado, o
   * `null` si no está. Quien la usa debe liberarla con `URL.revokeObjectURL`.
   */
  async urlLocal(url: string): Promise<string | null> {
    if (!this.disponible || !esVideoDescargable(url)) {
      return null;
    }
    const respuesta = await (await caches.open(CACHE_DESCARGAS)).match(url);
    return respuesta ? URL.createObjectURL(await respuesta.blob()) : null;
  }

  /** Cambia si el video se borra al terminar de verlo. */
  async cambiarBorrarAlTerminar(url: string, valor: boolean): Promise<void> {
    await this.guardar(this.lista().map((d) => (d.url === url ? { ...d, borrarAlTerminar: valor } : d)));
  }

  /** Borra una descarga del dispositivo. */
  async borrar(url: string): Promise<void> {
    if (!this.disponible) {
      return;
    }
    await (await caches.open(CACHE_DESCARGAS)).delete(url);
    await this.guardar(sinDescarga(this.lista(), url));
  }

  /** Borra todas las descargas del dispositivo. */
  async borrarTodas(): Promise<void> {
    if (!this.disponible) {
      return;
    }
    await caches.delete(CACHE_DESCARGAS);
    this.lista.set([]);
  }

  /** Espacio libre que el navegador permite usar, en bytes, o `null` si no lo informa. */
  async espacioLibre(): Promise<number | null> {
    const estimado = await navigator.storage?.estimate?.();
    if (!estimado?.quota) {
      return null;
    }
    return Math.max(0, estimado.quota - (estimado.usage ?? 0));
  }

  private async guardar(descargas: readonly Descarga[]): Promise<void> {
    const cache = await caches.open(CACHE_DESCARGAS);
    await guardarIndice(cache, descargas);
    this.lista.set(await leerIndice(cache));
  }

  private marcarProgreso(url: string, valor: number): void {
    this.progreso.update((p) => new Map(p).set(url, valor));
  }

  private quitarProgreso(url: string): void {
    this.progreso.update((p) => {
      const copia = new Map(p);
      copia.delete(url);
      return copia;
    });
  }
}
