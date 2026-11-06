import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Pregunta tal como la presenta el backend, sin la respuesta correcta (Req 7.6). */
export interface Pregunta {
  readonly id: number;
  readonly prompt: string;
  readonly options: readonly string[];
}

/** Evaluación de una ruta: enunciados y opciones, sin clave de respuestas (Req 7.1). */
export interface Evaluacion {
  readonly path_id: string;
  readonly questions: readonly Pregunta[];
}

/** Respuesta a una pregunta: índice de la opción elegida. */
export interface RespuestaItem {
  readonly question_id: number;
  readonly selected_option: number;
}

/** Resultado de un intento de evaluación (Req 7.2–7.5). */
export interface ResultadoIntento {
  readonly path_id: string;
  readonly score: number;
  readonly passed: boolean;
  readonly attempt_number: number;
  readonly attempts_remaining: number;
  readonly cooldown_until: string | null;
}

/**
 * Cliente del Assessment Service del backend. Solo realiza llamadas HTTP; la
 * validación de las respuestas y el cálculo del puntaje ocurren siempre en el
 * servidor (Req 7.6, 7.7), nunca en el cliente. La sesión viaja por la cookie
 * HttpOnly y el intento se ancla al Usuario autenticado en el backend
 * (anti-BOLA). Requisitos: 7.1–7.7.
 */
@Injectable({ providedIn: 'root' })
export class AssessmentService {
  private readonly http = inject(HttpClient);

  /** Obtiene la evaluación de una ruta (`GET /api/v1/evaluaciones/{rutaId}`). */
  async obtenerEvaluacion(rutaId: string): Promise<Evaluacion> {
    return firstValueFrom(
      this.http.get<Evaluacion>(`/api/v1/evaluaciones/${rutaId}`, {
        withCredentials: true,
      }),
    );
  }

  /**
   * Envía las respuestas de una ruta para calificación en el servidor
   * (`POST /api/v1/evaluaciones/{rutaId}/respuestas`).
   */
  async enviarRespuestas(
    rutaId: string,
    answers: readonly RespuestaItem[],
  ): Promise<ResultadoIntento> {
    return firstValueFrom(
      this.http.post<ResultadoIntento>(
        `/api/v1/evaluaciones/${rutaId}/respuestas`,
        { answers },
        { withCredentials: true },
      ),
    );
  }
}
