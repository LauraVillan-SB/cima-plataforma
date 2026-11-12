import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { GamificationService, Ranking } from './gamification.service';

/**
 * Ranking: tabla con las primeras posiciones y la posición del Usuario aunque
 * quede fuera del top. Solo muestra alias seudónimos; nunca teléfono, nombre
 * ni zona de otras personas. Las posiciones las calcula el backend.
 */
@Component({
  selector: 'cima-ranking-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="ranking">
      <h1 class="titulo">Ranking CIMA</h1>
      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando el ranking...</p>
      } @else if (error()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar el ranking. Intenta de nuevo.
        </div>
        <button type="button" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill" (click)="cargar()">Reintentar</button>
      } @else if (ranking(); as r) {
        <p class="resumen">{{ r.participants }} participantes aprendiendo contigo.</p>
        @if (r.entries.length === 0) {
          <p>Aún no hay posiciones para mostrar.</p>
        } @else {
          <table class="tabla">
            <caption class="solo-lector">Primeras posiciones del ranking</caption>
            <thead>
              <tr>
                <th scope="col">Puesto</th>
                <th scope="col">Participante</th>
                <th scope="col" class="col-nivel">Nivel</th>
                <th scope="col">Puntos</th>
              </tr>
            </thead>
            <tbody>
              @for (f of r.entries; track f.rank) {
                <tr [class.yo]="f.is_me">
                  <td>{{ f.rank }}</td>
                  <td>
                    {{ f.alias }}@if (f.is_me) { (tú) }
                    <span class="nivel-movil">{{ f.level_name }}</span>
                  </td>
                  <td class="col-nivel">{{ f.level_name }}</td>
                  <td>{{ f.total_points }}</td>
                </tr>
              }
            </tbody>
          </table>
        }
        @if (r.me; as yo) {
          @if (!estaEnTop(r)) {
            <p class="mi-puesto" role="status">
              Tu puesto: {{ yo.rank }} · {{ yo.total_points }} puntos
            </p>
          }
        }
      }
    </section>
  `,
  styles: [
    `
      .ranking { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.1rem; }
      .titulo { font-size: 1.5rem; }
      .resumen { color: var(--cima-texto-suave); }
      .tabla { width: 100%; border-collapse: collapse; background: #fff; border-radius: var(--cima-radio); overflow: hidden; }
      th { background: var(--cima-verde-oscuro); color: #fff; text-align: left; padding: 0.75rem; }
      td { padding: 0.75rem; border-top: 1px solid var(--cima-borde); overflow-wrap: break-word; }
      .nivel-movil { display: none; }
      /* En celular la columna de nivel se pasa debajo del alias para que la tabla quepa. */
      @media (max-width: 559px) {
        .tabla { table-layout: fixed; }
        th, td { padding: 0.6rem 0.5rem; }
        th:first-child { width: 4.2rem; }
        th:last-child { width: 4.8rem; }
        .col-nivel { display: none; }
        .nivel-movil { display: block; font-size: 0.85rem; font-weight: 400; color: var(--cima-texto-suave); }
      }
      .yo td { background: var(--cima-dorado); font-weight: 700; }
      .mi-puesto { background: var(--cima-dorado); border-radius: var(--cima-radio); padding: 0.75rem 1rem; font-weight: 700; }
      .solo-lector { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    `,
  ],
})
export class RankingPageComponent {
  private readonly gamificacion = inject(GamificationService);

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly ranking = signal<Ranking | null>(null);

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      this.ranking.set(await this.gamificacion.obtenerRanking(10));
    } catch {
      // Error genérico para el Usuario; el detalle lo registra el backend.
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  /** Verdadero si la fila del Usuario ya aparece dentro de la tabla. */
  estaEnTop(r: Ranking): boolean {
    return r.entries.some((f) => f.is_me);
  }
}
