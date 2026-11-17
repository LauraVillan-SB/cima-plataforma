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
  readonly title: string | null;
  readonly summary: string | null;
  readonly paragraphs: readonly string[];
  readonly key_points: readonly string[];
  readonly video: VideoCapsula | null;
  /** Video propio servido por el backend con sesión; opcional en datos guardados antes. */
  readonly video_file?: VideoArchivo | null;
}

/** Video propio de la cápsula; `url` es relativa y la arma el backend. */
export interface VideoArchivo {
  readonly url: string;
  readonly title: string;
}

/** Video complementario verificado; el texto de la cápsula funciona sin él. */
export interface VideoCapsula {
  readonly video_id: string;
  readonly title: string;
  readonly channel: string;
  readonly embed_url: string;
}

/** Estado de una cápsula dentro de una ruta, calculado por el backend. */
export type EstadoCapsula = 'completed' | 'next' | 'pending';

/** Cápsula en su posición dentro de una ruta. */
export interface ItemRuta {
  readonly position: number;
  readonly status: EstadoCapsula;
  readonly capsule: Microcapsula;
}

/** Ruta de aprendizaje con el avance real del Usuario (`GET /aprendizaje/rutas`). */
export interface Ruta {
  readonly path_id: string;
  readonly title: string | null;
  readonly summary: string | null;
  readonly audience_tags: readonly string[];
  readonly total_count: number;
  readonly completed_count: number;
  readonly completed: boolean;
  readonly next_microcapsule_id: string | null;
  readonly assessment_passed: boolean;
  readonly items: readonly ItemRuta[];
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
    elapsedSeconds?: number,
  ): Promise<ResultadoFinalizacion> {
    const cuerpo =
      elapsedSeconds === undefined
        ? { client_event_id: clientEventId, path_id: pathId }
        : {
            client_event_id: clientEventId,
            path_id: pathId,
            elapsed_seconds: elapsedSeconds,
          };
    return firstValueFrom(
      this.http.post<ResultadoFinalizacion>(
        `/api/v1/aprendizaje/microcapsulas/${microcapsulaId}/finalizar`,
        cuerpo,
        { withCredentials: true },
      ),
    );
  }

  /**
   * Obtiene las rutas publicadas con el avance real del Usuario
   * (`GET /api/v1/aprendizaje/rutas`). El estado de cada cápsula
   * (completada, siguiente, pendiente) lo calcula el backend.
   */
  async obtenerRutas(): Promise<readonly Ruta[]> {
    const respuesta = await firstValueFrom(
      this.http.get<{ routes: Ruta[] }>('/api/v1/aprendizaje/rutas', {
        withCredentials: true,
      }),
    );
    return respuesta.routes;
  }
}
