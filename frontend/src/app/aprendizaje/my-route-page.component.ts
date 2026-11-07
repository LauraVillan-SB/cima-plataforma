import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LearningService, Ruta } from './learning.service';
import { etiquetaTema, minutos } from './temas';

/**
 * Mi ruta: línea de tiempo con las cápsulas reales de cada ruta y su estado
 * (completada, siguiente, pendiente). Al completar todas las cápsulas ofrece
 * la evaluación. Solo presentación; el avance lo calcula el backend (Req 17.3).
 */
@Component({
  selector: 'cima-my-route-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="mi-ruta">
      <h1 class="titulo">Mi ruta de aprendizaje</h1>
      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando tu ruta...</p>
      } @else if (error()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar tu ruta. Revisa tu conexión e intenta de nuevo.
        </div>
        <button type="button" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill" (click)="cargar()">Reintentar</button>
      } @else if (rutas().length === 0) {
        <p>Todavía no hay rutas para mostrar.</p>
      } @else {
        @for (r of rutas(); track r.path_id) {
          <article class="ruta">
            <h2 class="ruta__titulo">{{ r.title ?? 'Ruta de aprendizaje' }}</h2>
            @if (r.summary) {
              <p class="ruta__resumen">{{ r.summary }}</p>
            }
            <p class="ruta__avance">{{ r.completed_count }} de {{ r.total_count }} completadas</p>
            <ol class="linea">
              @for (i of r.items; track i.capsule.id) {
                <li class="estacion" [class.estacion--lista]="i.status === 'completed'"
                    [class.estacion--actual]="i.status === 'next'">
                  <span class="estacion__marca" aria-hidden="true">
                    {{ i.status === 'completed' ? '✓' : i.position }}
                  </span>
                  <div class="estacion__cuerpo">
                    <h3 class="estacion__titulo">{{ i.capsule.title ?? etiqueta(i.capsule.topic) }}</h3>
                    <p class="estacion__meta">
                      {{ etiqueta(i.capsule.topic) }} · {{ mins(i.capsule.duration_sec) }} min ·
                      {{ textoEstado(i.status) }}
                    </p>
                    @if (i.status !== 'pending') {
                      <a class="enlace" [routerLink]="['/aprendizaje/leccion', r.path_id, i.capsule.id]">
                        {{ i.status === 'completed' ? 'Repasar' : 'Continuar' }}
                      </a>
                    }
                  </div>
                </li>
              }
            </ol>
            @if (r.completed && !r.assessment_passed) {
              <a class="sb-ui-button sb-ui-button--primary sb-ui-button--fill accion" [routerLink]="['/evaluacion', r.path_id]">
                Presentar evaluación
              </a>
            }
            @if (r.assessment_passed) {
              <p class="aprobada" role="status">¡Aprobaste la evaluación de esta ruta!</p>
            }
          </article>
        }
      }
    </section>
  `,
  styles: [
    `
      .mi-ruta { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.1rem; }
      .titulo { font-size: 1.5rem; }
      .ruta { background: var(--cima-superficie); border: 1px solid var(--cima-borde); border-radius: var(--cima-radio); padding: 1.25rem; margin-bottom: 1.5rem; }
      .ruta__titulo { margin: 0 0 0.25rem; color: var(--cima-verde-oscuro); }
      .ruta__resumen, .ruta__avance { margin: 0 0 0.5rem; color: var(--cima-texto-suave); }
      .linea { list-style: none; margin: 1rem 0; padding: 0; border-left: 4px solid var(--cima-borde); }
      .estacion { display: flex; gap: 0.75rem; padding: 0 0 1.25rem 0; margin-left: -18px; }
      .estacion__marca { flex: none; width: 32px; height: 32px; border-radius: 50%; background: #fff; border: 3px solid var(--cima-borde); display: grid; place-items: center; font-weight: 700; }
      .estacion--lista .estacion__marca { background: var(--cima-verde); border-color: var(--cima-verde); color: #fff; }
      .estacion--actual .estacion__marca { border-color: var(--cima-dorado); background: var(--cima-verde-oscuro); color: var(--cima-dorado); }
      .estacion__titulo { margin: 0; font-size: 1.1rem; }
      .estacion__meta { margin: 0.15rem 0; color: var(--cima-texto-suave); }
      .enlace { display: inline-flex; align-items: center; color: var(--cima-verde-oscuro); font-weight: 700; }
      .accion { display: inline-flex; align-items: center; justify-content: center; width: 100%; text-decoration: none; }
      .aprobada { font-weight: 700; color: var(--cima-verde-oscuro); }
    `,
  ],
})
export class MyRoutePageComponent {
  private readonly learning = inject(LearningService);

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly rutas = signal<readonly Ruta[]>([]);

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      this.rutas.set(await this.learning.obtenerRutas());
    } catch {
      // Error genérico para el Usuario; el detalle lo registra el backend.
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  etiqueta(topic: string): string {
    return etiquetaTema(topic);
  }

  mins(segundos: number): number {
    return minutos(segundos);
  }

  textoEstado(estado: string): string {
    if (estado === 'completed') {
      return 'Completada';
    }
    return estado === 'next' ? 'Te toca ahora' : 'Pendiente';
  }
}
