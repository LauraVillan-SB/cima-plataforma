import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { mensajeDeError } from '../core/mensaje-error';
import { GamificationService, Reconocimientos } from './gamification.service';

/**
 * Pantalla de reconocimientos (Tarea 23.3, Req 19.7): muestra las insignias y
 * los puntos del Usuario autenticado. Solo lectura; el backend decide qué se
 * otorga y no expone datos de otros Perfiles. Sin PII.
 */
@Component({
  selector: 'cima-gamification-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    <section class="reconocimientos">
      <h1 class="titulo">Tus logros</h1>

      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Cargando tus logros...</p>
      } @else if (mensajeError(); as msg) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          {{ msg }}
          <button type="button" class="sb-ui-button sb-ui-button--secondary" (click)="cargar()">
            Reintentar
          </button>
        </div>
      } @else if (datos(); as d) {
        <p class="puntos">
          Llevas <strong>{{ d.total_points }}</strong> {{ d.total_points === 1 ? 'punto' : 'puntos' }}.
        </p>

        @if (d.badges.length === 0) {
          <p class="estado">
            Aún no tienes insignias. Termina tu primera microcápsula y ganas la primera.
          </p>
          <a
            class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large"
            routerLink="/aprendizaje"
          >
            Ir a mis microcápsulas
          </a>
        } @else {
          <ul class="insignias">
            @for (b of d.badges; track b.badge_code) {
              <li class="insignia sb-ui-card">
                <span aria-hidden="true">🏅</span> {{ b.badge_name }}
              </li>
            }
          </ul>
        }
      }
    </section>
  `,
  styles: [
    `
      .reconocimientos {
        padding: 1.5rem 1rem;
        max-width: 560px;
        margin: 0 auto;
      }
      .titulo {
        margin: 0 0 1rem;
      }
      .estado,
      .puntos {
        line-height: 1.5;
      }
      .insignias {
        list-style: none;
        margin: 1rem 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }
      .insignia {
        padding: 1rem;
        font-size: 1.1rem;
      }
    `,
  ],
})
export class GamificationPageComponent {
  private readonly gamificacion = inject(GamificationService);

  readonly cargando = signal<boolean>(true);
  readonly mensajeError = signal<string | null>(null);
  readonly datos = signal<Reconocimientos | null>(null);

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.mensajeError.set(null);
    try {
      this.datos.set(await this.gamificacion.obtenerReconocimientos());
    } catch (fallo) {
      this.mensajeError.set(
        mensajeDeError(fallo, 'No pudimos cargar tus logros. Revisa tu conexión e intenta de nuevo.'),
      );
    } finally {
      this.cargando.set(false);
    }
  }
}
