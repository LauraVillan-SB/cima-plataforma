import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Insignia ganada por el Usuario. */
export interface Insignia {
  readonly badge_code: string;
  readonly badge_name: string;
}

/** Insignias y puntos del Usuario autenticado (Req 19.7); sin PII. */
export interface Reconocimientos {
  readonly badges: readonly Insignia[];
  readonly total_points: number;
}

/**
 * Cliente del Gamification Service. Solo lectura: los reconocimientos los
 * otorga el backend al completar contenido, nunca el cliente (Req 19.3). No se
 * envía `perfil_id`: el titular sale de la cookie HttpOnly (anti-BOLA).
 */
@Injectable({ providedIn: 'root' })
export class GamificationService {
  private readonly http = inject(HttpClient);

  /** `GET /api/v1/gamificacion/reconocimientos` */
  async obtenerReconocimientos(): Promise<Reconocimientos> {
    return firstValueFrom(
      this.http.get<Reconocimientos>('/api/v1/gamificacion/reconocimientos', {
        withCredentials: true,
      }),
    );
  }
}
