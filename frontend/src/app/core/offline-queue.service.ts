import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { NetworkStatusService } from './network-status.service';

/** Tipos de accion que la cola puede encolar (consistente con el backend). */
export type AccionTipo = 'microcapsula_finalizada' | 'evaluacion_respondida';

/** Accion encolada localmente con su clave de idempotencia (Req 18.2). */
export interface AccionEncolada {
  client_event_id: string;
  action_type: AccionTipo;
  payload: Record<string, unknown>;
  enqueued_at: string;
}

/** Estado de sincronizacion expresado en lenguaje simple (Req 18.5). */
export type EstadoSync = 'al_dia' | 'pendiente' | 'sincronizando' | 'sin_conexion';

const STORAGE_KEY = 'cima.offline.queue';

/**
 * Cola local idempotente de acciones offline.
 *
 * Encola acciones con un `client_event_id` (UUID v4) y las envía en lote a
 * `POST /api/v1/sync/acciones` cuando hay red; el backend aplica el lote de
 * forma idempotente, por lo que reintentar no duplica (Req 18.2, 18.4). El
 * estado se expone en lenguaje simple para la UI (Req 18.5). Solo presentación.
 */
@Injectable({ providedIn: 'root' })
export class OfflineQueueService {
  private readonly http = inject(HttpClient);
  private readonly red = inject(NetworkStatusService);

  private readonly cola = signal<AccionEncolada[]>(this.leerDeAlmacen());

  /** Cantidad de acciones pendientes de sincronizar. */
  readonly pendientes = computed(() => this.cola().length);

  /** Estado de sincronizacion en lenguaje simple para mostrar al Usuario. */
  readonly estado = computed<EstadoSync>(() => {
    if (!this.red.online()) {
      return 'sin_conexion';
    }
    return this.cola().length === 0 ? 'al_dia' : 'pendiente';
  });

  /** Genera una clave de idempotencia (UUID v4) para una accion encolada. */
  static generarClaveIdempotencia(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /** Encola una accion para sincronizar luego; persiste en almacenamiento local. */
  encolar(tipo: AccionTipo, payload: Record<string, unknown>): AccionEncolada {
    const accion: AccionEncolada = {
      client_event_id: OfflineQueueService.generarClaveIdempotencia(),
      action_type: tipo,
      payload,
      enqueued_at: new Date().toISOString(),
    };
    this.cola.update((actual) => [...actual, accion]);
    this.persistir();
    return accion;
  }

  /**
   * Sincroniza el lote pendiente con el backend si hay red. El backend es
   * idempotente por `client_event_id`, así que es seguro reintentar; solo se
   * vacía la cola cuando el envío fue exitoso (sin pérdida, Req 18.4).
   */
  async sincronizar(profileId: string): Promise<void> {
    const lote = this.cola();
    if (lote.length === 0 || !this.red.online()) {
      return;
    }
    const body = {
      profile_id: profileId,
      actions: lote.map((a) => ({
        client_event_id: a.client_event_id,
        action_type: a.action_type,
        payload: a.payload,
      })),
    };
    await firstValueFrom(this.http.post('/api/v1/sync/acciones', body));
    // Exito: se vacia la cola. Si fallara, la cola se conserva para reintentar.
    this.cola.set([]);
    this.persistir();
  }

  private leerDeAlmacen(): AccionEncolada[] {
    if (typeof localStorage === 'undefined') {
      return [];
    }
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as AccionEncolada[]) : [];
    } catch {
      return [];
    }
  }

  private persistir(): void {
    if (typeof localStorage === 'undefined') {
      return;
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.cola()));
  }
}
