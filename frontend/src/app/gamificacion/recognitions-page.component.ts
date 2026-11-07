import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { GamificationService } from './gamification.service';

/**
 * Reconocimientos: insignias del catálogo (obtenidas y por obtener), puntos,
 * racha y nivel reales. No hay canje ni beneficios: CIMA educa y mide interés,
 * no procesa pagos. Los reconocimientos solo los otorga el backend (Req 19.3).
 */
@Component({
  selector: 'cima-recognitions-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="reconocimientos">
      <h1 class="titulo">Mis reconocimientos</h1>
      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando tus reconocimientos...</p>
      } @else if (error()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar tus reconocimientos. Intenta de nuevo.
        </div>
        <button type="button" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill" (click)="cargar()">Reintentar</button>
      } @else if (resumen(); as r) {
        <div class="nivel">
          <p class="nivel__nombre">Nivel {{ r.level.number }} · {{ r.level.name }}</p>
          <p class="nivel__puntos">{{ r.total_points }} puntos · {{ r.streak_days }} días seguidos</p>
          <div class="barra" role="progressbar" aria-label="Avance al siguiente nivel"
               [attr.aria-valuenow]="r.level_progress_pct" aria-valuemin="0" aria-valuemax="100">
            <div class="barra__relleno" [style.width.%]="r.level_progress_pct"></div>
          </div>
          @if (r.next_level; as n) {
            <p class="nivel__falta">Te faltan {{ n.points_needed }} puntos para el nivel {{ n.name }}.</p>
          }
        </div>
        <ul class="insignias">
          @for (b of r.badges; track b.badge_code) {
            <li class="insignia" [class.insignia--ganada]="b.earned">
              <span class="insignia__icono" aria-hidden="true">{{ b.earned ? '🏅' : '🔒' }}</span>
              <div>
                <h2 class="insignia__nombre">{{ b.badge_name }}</h2>
                <p class="insignia__meta">
                  {{ b.earned ? 'Obtenida' : 'Por obtener' }} · {{ b.points }} puntos
                </p>
              </div>
            </li>
          }
        </ul>
      }
    </section>
  `,
  styles: [
    `
      .reconocimientos { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.1rem; }
      .titulo { font-size: 1.5rem; }
      .nivel { background: var(--cima-verde-oscuro); color: #fff; border-radius: var(--cima-radio); padding: 1.25rem; margin-bottom: 1rem; }
      .nivel__nombre { margin: 0; font-size: 1.4rem; font-weight: 700; color: var(--cima-dorado); }
      .nivel__puntos, .nivel__falta { margin: 0.25rem 0 0.75rem; }
      .barra { background: rgba(255,255,255,0.25); border-radius: 999px; height: 12px; overflow: hidden; }
      .barra__relleno { background: var(--cima-dorado); height: 100%; }
      .insignias { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.75rem; }
      .insignia { display: flex; gap: 1rem; align-items: center; background: #fff; border: 1px solid var(--cima-borde); border-radius: var(--cima-radio); padding: 1rem; }
      .insignia--ganada { background: var(--cima-verde-claro); border-color: var(--cima-verde); }
      .insignia__icono { font-size: 2rem; }
      .insignia__nombre { margin: 0; font-size: 1.1rem; }
      .insignia__meta { margin: 0; color: var(--cima-texto-suave); }
    `,
  ],
})
export class RecognitionsPageComponent {
  private readonly gamificacion = inject(GamificationService);

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly resumen = this.gamificacion.resumen;

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      await this.gamificacion.cargarResumen();
    } catch {
      // Error genérico para el Usuario; el detalle lo registra el backend.
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }
}
