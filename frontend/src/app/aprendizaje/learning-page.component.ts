import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import {
  LearningService,
  Microcapsula,
  SeleccionMicrocapsulas,
} from './learning.service';

/** Etiqueta legible en español coloquial de cada tema de microcápsula (Req 4.2). */
const ETIQUETA_TEMA: Record<string, string> = {
  gestion_riesgos: 'Gestión de riesgos',
  finanzas: 'Finanzas',
  adaptacion_clima: 'Adaptación al clima',
};

/**
 * Pantalla de aprendizaje: muestra las microcápsulas personalizadas del Usuario
 * (Tarea 23.3, Req 4). Solo presentación: la selección, el orden y la
 * personalización las resuelve el backend (Req 17.3); aquí se listan y se
 * muestra, si aplica, el aviso de contenido general cuando no hay específico
 * (Req 4.5). No muestra PII.
 */
@Component({
  selector: 'cima-learning-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="aprendizaje">
      <h1 class="titulo">Tus microcápsulas</h1>

      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Cargando tu contenido...</p>
      } @else if (error()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar tus microcápsulas. Revisa tu conexión e intenta de nuevo.
        </div>
        <button
          type="button"
          class="sb-ui-button sb-ui-button--primary"
          (click)="cargar()"
        >
          Reintentar
        </button>
      } @else {
        @if (aviso()) {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">{{ aviso() }}</div>
        }
        @if (microcapsulas().length === 0) {
          <p class="estado">Todavía no hay microcápsulas para mostrar.</p>
        } @else {
          <ul class="lista">
            @for (m of microcapsulas(); track m.id) {
              <li class="sb-ui-card tarjeta">
                <div class="sb-ui-card__body">
                  <span class="tema">{{ etiquetaTema(m.topic) }}</span>
                  <p class="duracion">{{ minutos(m.duration_sec) }} min</p>
                </div>
              </li>
            }
          </ul>
        }
      }
    </section>
  `,
  styles: [
    `
      .aprendizaje {
        padding: 1.5rem 1rem;
        max-width: 560px;
        margin: 0 auto;
      }
      .titulo {
        font-size: 1.25rem;
        margin: 0 0 1rem;
      }
      .estado {
        line-height: 1.5;
      }
      .lista {
        list-style: none;
        margin: 1rem 0 0;
        padding: 0;
        display: grid;
        gap: 0.75rem;
      }
      .tarjeta {
        background: #fff;
        padding: 1rem;
      }
      .tema {
        font-weight: 600;
      }
      .duracion {
        margin: 0.25rem 0 0;
        color: #555;
      }
    `,
  ],
})
export class LearningPageComponent {
  private readonly learning = inject(LearningService);

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly microcapsulas = signal<readonly Microcapsula[]>([]);
  readonly aviso = signal<string | null>(null);

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      const seleccion: SeleccionMicrocapsulas =
        await this.learning.obtenerMicrocapsulas();
      this.microcapsulas.set(seleccion.items);
      this.aviso.set(seleccion.notice);
    } catch {
      // Error genérico para el Usuario; el detalle lo registra el backend.
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  etiquetaTema(topic: string): string {
    return ETIQUETA_TEMA[topic] ?? topic;
  }

  minutos(segundos: number): number {
    return Math.round(segundos / 60);
  }
}
