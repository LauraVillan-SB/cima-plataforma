import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Nivel del titular, derivado de sus puntos en el backend. */
export interface Nivel {
  readonly number: number;
  readonly name: string;
  readonly min_points: number;
}

/** Siguiente nivel y puntos que faltan para alcanzarlo. */
export interface SiguienteNivel {
  readonly number: number;
  readonly name: string;
  readonly points_needed: number;
}

/** Insignia del catálogo, marcada si el titular ya la obtuvo (Req 19). */
export interface Insignia {
  readonly badge_code: string;
  readonly badge_name: string;
  readonly points: number;
  readonly earned: boolean;
}

/** Insignia ganada por el Usuario, tal como la lista `reconocimientos`. */
export interface InsigniaGanada {
  readonly badge_code: string;
  readonly badge_name: string;
}

/** Insignias ganadas y puntos del Usuario autenticado (Req 19.7); sin PII. */
export interface Reconocimientos {
  readonly badges: readonly InsigniaGanada[];
  readonly total_points: number;
}

/** Resumen de gamificación del titular (`GET /api/v1/gamificacion/resumen`). */
export interface ResumenGamificacion {
  readonly total_points: number;
  readonly streak_days: number;
  readonly level: Nivel;
  readonly next_level: SiguienteNivel | null;
  readonly level_progress_pct: number;
  readonly badges: readonly Insignia[];
}

/** Fila del ranking; el alias es seudónimo, sin datos personales. */
export interface FilaRanking {
  readonly rank: number;
  readonly alias: string;
  readonly total_points: number;
  readonly level_name: string;
  readonly streak_days: number;
  readonly is_me: boolean;
}

/** Ranking acotado y la posición del titular (`GET /api/v1/gamificacion/ranking`). */
export interface Ranking {
  readonly entries: readonly FilaRanking[];
  readonly me: FilaRanking | null;
  readonly participants: number;
}

/**
 * Cliente del Gamification Service. Solo lectura: puntos, nivel, racha,
 * insignias y ranking los calcula el backend al completar contenido; el
 * cliente nunca otorga reconocimientos (Req 19.3). No se envía `perfil_id`: el
 * titular sale de la cookie HttpOnly (anti-BOLA). Expone el resumen en una
 * señal para que el encabezado y las vistas lo compartan.
 */
@Injectable({ providedIn: 'root' })
export class GamificationService {
  private readonly http = inject(HttpClient);

  /** Último resumen cargado; null mientras no haya sesión o no se haya cargado. */
  readonly resumen = signal<ResumenGamificacion | null>(null);

  /** `GET /api/v1/gamificacion/reconocimientos` */
  async obtenerReconocimientos(): Promise<Reconocimientos> {
    return firstValueFrom(
      this.http.get<Reconocimientos>('/api/v1/gamificacion/reconocimientos', {
        withCredentials: true,
      }),
    );
  }

  /** Carga el resumen del Usuario autenticado y lo publica en la señal. */
  async cargarResumen(): Promise<ResumenGamificacion> {
    const resumen = await firstValueFrom(
      this.http.get<ResumenGamificacion>('/api/v1/gamificacion/resumen', {
        withCredentials: true,
      }),
    );
    this.resumen.set(resumen);
    return resumen;
  }

  /** Limpia el estado al cerrar sesión para no mostrar datos de otra persona. */
  limpiar(): void {
    this.resumen.set(null);
  }

  /** Obtiene el ranking (`tamano` entre 1 y 50). */
  async obtenerRanking(tamano = 10): Promise<Ranking> {
    return firstValueFrom(
      this.http.get<Ranking>('/api/v1/gamificacion/ranking', {
        params: { tamano },
        withCredentials: true,
      }),
    );
  }
}
