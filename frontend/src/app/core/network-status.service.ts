import { Injectable, signal } from '@angular/core';

/**
 * Detecta el estado de la conexión y expone un indicador reactivo.
 *
 * Marca "sin conexión" solo cuando la interrupción supera un umbral (≥ 3 s)
 * para evitar parpadeos ante microcortes, y refleja el estado en ≤ 2 s
 * (Req 2.8, 2.9). Solo presentación: no contiene lógica de negocio.
 */
@Injectable({ providedIn: 'root' })
export class NetworkStatusService {
  /** Umbral de interrupcion sostenida antes de declarar "sin conexion" (ms). */
  private static readonly OFFLINE_THRESHOLD_MS = 3000;

  /** `true` cuando hay conexion; `false` cuando se perdio de forma sostenida. */
  readonly online = signal<boolean>(
    typeof navigator !== 'undefined' ? navigator.onLine : true,
  );

  private offlineTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    if (typeof window === 'undefined') {
      return;
    }
    window.addEventListener('online', () => this.alReconectar());
    window.addEventListener('offline', () => this.alDesconectar());
  }

  /** Reconexion: cancela el temporizador pendiente y marca en linea de inmediato. */
  private alReconectar(): void {
    if (this.offlineTimer !== null) {
      clearTimeout(this.offlineTimer);
      this.offlineTimer = null;
    }
    this.online.set(true);
  }

  /**
   * Desconexion: espera a que la interrupcion sea sostenida (≥ umbral) antes de
   * declarar "sin conexion", de modo que un microcorte no cambie el indicador.
   */
  private alDesconectar(): void {
    if (this.offlineTimer !== null) {
      return;
    }
    this.offlineTimer = setTimeout(() => {
      this.online.set(false);
      this.offlineTimer = null;
    }, NetworkStatusService.OFFLINE_THRESHOLD_MS);
  }
}
