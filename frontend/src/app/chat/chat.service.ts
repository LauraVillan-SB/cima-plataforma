import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { extensionDeMime } from './chat';

/** Acuse 202 tras encolar un mensaje (Req 3.5). */
export interface MensajeAceptado {
  readonly id: string;
  readonly status: string;
  readonly processing_after_seconds: number;
  /** Solo en notas de voz: lo que se entendió, ya sin datos personales. */
  readonly input_redacted?: string | null;
}

/**
 * Estado o resultado de una inferencia. `response_text` solo viene cuando el
 * estado es "listo" y ya trae el prefijo que identifica a la IA (Req 16.5).
 */
export interface ResultadoMensaje {
  readonly id: string;
  readonly status: string;
  readonly input_channel: string;
  readonly response_text: string | null;
  readonly response_audio_ref: string | null;
}

/** Entrada del historial; el texto ya viene con la PII redactada (Req 3.8). */
export interface EntradaHistorial {
  readonly id: string;
  readonly status: string;
  readonly input_channel: string;
  readonly input_redacted: string;
  readonly response_text: string | null;
}

export interface Historial {
  readonly items: readonly EntradaHistorial[];
}

/**
 * Cliente del Conversational Agent Service. Solo hace llamadas HTTP: la
 * redacción de PII, los guardrails y el prefijo de IA los aplica el backend, y
 * el titular se resuelve por la cookie HttpOnly (anti-BOLA). No hay SSE ni
 * WebSocket: el estado se consulta con `consultar`. Requisitos: 3.5–3.8, 14.2.
 */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly http = inject(HttpClient);

  /** `POST /api/v1/chat/mensajes` */
  async enviarTexto(text: string): Promise<MensajeAceptado> {
    return firstValueFrom(
      this.http.post<MensajeAceptado>(
        '/api/v1/chat/mensajes',
        { text },
        { withCredentials: true },
      ),
    );
  }

  /**
   * `POST /api/v1/chat/mensajes/voz` (multipart). No se fija Content-Type: el
   * navegador agrega el límite del multipart. La duración la mide el cliente y
   * el servidor la valida contra el rango permitido.
   */
  async enviarVoz(audio: Blob, mime: string, duracionSegundos: number): Promise<MensajeAceptado> {
    const cuerpo = new FormData();
    cuerpo.append('audio', audio, `nota.${extensionDeMime(mime)}`);
    cuerpo.append('duracion_segundos', String(duracionSegundos));
    return firstValueFrom(
      this.http.post<MensajeAceptado>('/api/v1/chat/mensajes/voz', cuerpo, {
        withCredentials: true,
      }),
    );
  }

  /** `GET /api/v1/chat/mensajes/{id}` */
  async consultar(id: string): Promise<ResultadoMensaje> {
    return firstValueFrom(
      this.http.get<ResultadoMensaje>(`/api/v1/chat/mensajes/${encodeURIComponent(id)}`, {
        withCredentials: true,
      }),
    );
  }

  /** `GET /api/v1/chat/historial` (del más antiguo al más reciente). */
  async historial(): Promise<Historial> {
    return firstValueFrom(
      this.http.get<Historial>('/api/v1/chat/historial', { withCredentials: true }),
    );
  }
}
