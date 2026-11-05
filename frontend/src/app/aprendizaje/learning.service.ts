import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/**
 * Microcápsula tal como la entrega el backend (`GET /api/v1/aprendizaje/microcapsulas`).
 * El backend garantiza por contrato que la duración está entre 180 y 300 s y que
 * el tema es uno de la allowlist (Req 4.1, 4.2). Este dominio no maneja PII.
 */
export interface Microcapsula {
  readonly id: string;
  readonly topic: string;
  readonly activity_tags: readonly string[];
  readonly duration_sec: number;
  readonly difficulty: number;
}

/**
 * Selección personalizada de microcápsulas. `fallback` indica que no había
 * contenido para la actividad del Perfil y se entregó el tema general;
 * `prompt_activity` que el Perfil está incompleto; `notice` es el aviso en
 * español coloquial para mostrar al Usuario (Req 4.4, 4.5, 4.8).
 */
export interface SeleccionMicrocapsulas {
  readonly items: readonly Microcapsula[];
  readonly fallback: boolean;
  readonly prompt_activity: boolean;
  readonly notice: string | null;
}

/** Resultado de registrar la finalización de una microcápsula (Req 4.6, 4.10). */
export interface ResultadoFinalizacion {
  readonly path_id: string;
  readonly microcapsule_id: string;
  readonly path_completed: boolean;
  readonly completed_count: number;
  readonly total_count: number;
}

/**
 * Cliente del Learning Service del backend. Solo realiza llamadas HTTP; sin
 * lógica de negocio ni autorización en el cliente: la selección personalizada,
 * el orden y la completitud los resuelve el backend (Req 17.3). La sesión viaja
 * por la cookie HttpOnly. Requisitos: 4.1–4.10.
 */
@Injectable({ providedIn: 'root' })
export class LearningService {
  private readonly http = inject(HttpClient);

  /**
   * Obtiene las microcápsulas personalizadas del Usuario autenticado
   * (`GET /api/v1/aprendizaje/microcapsulas`). El backend elige según el Perfil.
   */
  async obtenerMicrocapsulas(): Promise<SeleccionMicrocapsulas> {
    return firstValueFrom(
      this.http.get<SeleccionMicrocapsulas>('/api/v1/aprendizaje/microcapsulas', {
        withCredentials: true,
      }),
    );
  }

  /**
   * Registra la finalización de una microcápsula dentro de una ruta
   * (`POST /api/v1/aprendizaje/microcapsulas/{id}/finalizar`). Idempotente por
   * `client_event_id` generado en el cliente (Req 4.7).
   */
  async finalizar(
    microcapsulaId: string,
    pathId: string,
    clientEventId: string,
  ): Promise<ResultadoFinalizacion> {
    return firstValueFrom(
      this.http.post<ResultadoFinalizacion>(
        `/api/v1/aprendizaje/microcapsulas/${microcapsulaId}/finalizar`,
        { client_event_id: clientEventId, path_id: pathId },
        { withCredentials: true },
      ),
    );
  }
}
