import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { CuerpoRespuesta, PreguntaEncuesta } from './encuesta';

/** Encuesta de una ruta tal como la presenta el backend (Req 20.1, 20.7). */
export interface PresentacionEncuesta {
  readonly survey_id: string;
  readonly path_id: string;
  readonly questions: readonly PreguntaEncuesta[];
  readonly already_answered: boolean;
}

/** Acuse del registro: el backend no devuelve el comentario (Req 20.5). */
export interface RespuestaRegistrada {
  readonly id: string;
  readonly path_id: string;
  readonly rating: number;
  readonly geo_zone: string;
}

/**
 * Cliente del Survey Service. Solo hace llamadas HTTP: el backend verifica que la
 * ruta esté completa, valida las respuestas, redacta la PII del comentario y ancla
 * todo al Usuario de la sesión (anti-BOLA). La sesión viaja en la cookie HttpOnly.
 * Requisitos: 20.1–20.7.
 */
@Injectable({ providedIn: 'root' })
export class SurveyService {
  private readonly http = inject(HttpClient);

  /** Encuesta de la ruta (`GET /api/v1/encuestas/{rutaId}`). */
  async obtener(rutaId: string): Promise<PresentacionEncuesta> {
    return firstValueFrom(
      this.http.get<PresentacionEncuesta>(`/api/v1/encuestas/${rutaId}`, { withCredentials: true }),
    );
  }

  /**
   * Envía la respuesta (`POST /api/v1/encuestas/{rutaId}/respuestas`). Es idempotente
   * por `client_event_id`: reintentar con el mismo cuerpo no la duplica (Req 20.6).
   */
  async responder(rutaId: string, cuerpo: CuerpoRespuesta): Promise<RespuestaRegistrada> {
    return firstValueFrom(
      this.http.post<RespuestaRegistrada>(`/api/v1/encuestas/${rutaId}/respuestas`, cuerpo, {
        withCredentials: true,
      }),
    );
  }
}
