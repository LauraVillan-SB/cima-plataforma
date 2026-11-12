import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { GamificationService } from '../gamificacion/gamification.service';
import { EstadoCapsula, LearningService, Microcapsula, Ruta } from './learning.service';
import { etiquetaTema, minutos } from './temas';

/** Tarjeta del tablero: una cápsula con su ruta y su estado real. */
interface TarjetaCapsula {
  readonly pathId: string;
  readonly rutaTitulo: string;
  readonly estado: EstadoCapsula;
  readonly capsula: Microcapsula;
}

/**
 * Tablero de aprendizaje (Tarea 23.3, Req 4). Muestra el avance real, filtros
 * por tema y las cápsulas de las rutas con su estado. Solo presentación: el
 * orden, el estado y la completitud los calcula el backend (Req 17.3). Sin PII.
 */
@Component({
  selector: 'cima-learning-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="tablero">
      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Cargando tu contenido...</p>
      } @else if (error()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar tus microcápsulas. Revisa tu conexión e intenta de nuevo.
        </div>
        <button type="button" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill" (click)="cargar()">
          Reintentar
        </button>
      } @else {
        <div class="banner">
          <h1 class="banner__titulo">¡Hola! Sigue aprendiendo a tu ritmo</h1>
          <p class="banner__texto">
            Llevas {{ completadas() }} de {{ total() }} microcápsulas.
            @if (resumen(); as r) {
              @if (r.next_level; as n) {
                Te faltan {{ n.points_needed }} puntos para el nivel {{ n.name }}.
              } @else {
                Alcanzaste el nivel más alto.
              }
            }
          </p>
          <div class="barra" role="progressbar" aria-label="Avance de microcápsulas"
               [attr.aria-valuenow]="porcentaje()" aria-valuemin="0" aria-valuemax="100">
            <div class="barra__relleno" [style.width.%]="porcentaje()"></div>
          </div>
        </div>

        @if (aviso()) {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">{{ aviso() }}</div>
        }

        <div class="filtros" role="group" aria-label="Filtrar por tema">
          <button type="button" class="filtro" [class.filtro--activo]="filtro() === ''"
                  [attr.aria-pressed]="filtro() === ''" (click)="filtro.set('')">Todos</button>
          @for (t of temas(); track t) {
            <button type="button" class="filtro" [class.filtro--activo]="filtro() === t"
                    [attr.aria-pressed]="filtro() === t" (click)="filtro.set(t)">{{ etiqueta(t) }}</button>
          }
        </div>

        @if (visibles().length === 0) {
          <p class="estado">Todavía no hay microcápsulas para mostrar.</p>
        } @else {
          <ul class="lista">
            @for (t of visibles(); track t.pathId + t.capsula.id) {
              <li class="tarjeta" [class.tarjeta--lista]="t.estado === 'completed'">
                <span class="tarjeta__tema">{{ etiqueta(t.capsula.topic) }}</span>
                <h2 class="tarjeta__titulo">{{ t.capsula.title ?? etiqueta(t.capsula.topic) }}</h2>
                @if (t.capsula.summary) {
                  <p class="tarjeta__texto">{{ t.capsula.summary }}</p>
                }
                <p class="tarjeta__meta">
                  {{ mins(t.capsula.duration_sec) }} min · {{ t.rutaTitulo }}
                </p>
                <p class="tarjeta__estado">{{ textoEstado(t.estado) }}</p>
                @if (t.estado === 'pending') {
                  <button type="button" class="sb-ui-button sb-ui-button--secondary" disabled>
                    Completa la anterior
                  </button>
                } @else {
                  <a class="sb-ui-button sb-ui-button--primary sb-ui-button--fill"
                     [routerLink]="['/aprendizaje/leccion', t.pathId, t.capsula.id]">
                    {{ t.estado === 'completed' ? 'Repasar' : 'Empezar' }}
                  </a>
                }
              </li>
            }
          </ul>
        }
      }
    </section>
  `,
  styles: [
    `
      .tablero { padding: 1rem; max-width: 960px; margin: 0 auto; }
      .estado { line-height: 1.5; font-size: 1.1rem; }
      .banner { background: var(--cima-verde-oscuro); color: #fff; border-radius: var(--cima-radio); padding: 1.25rem; margin-bottom: 1rem; }
      .banner__titulo { margin: 0 0 0.5rem; font-size: 1.4rem; color: var(--cima-dorado); }
      .banner__texto { margin: 0 0 0.75rem; font-size: 1.1rem; }
      .barra { background: rgba(255,255,255,0.25); border-radius: 999px; height: 12px; overflow: hidden; }
      .barra__relleno { background: var(--cima-dorado); height: 100%; transition: width 0.3s; }
      .filtros { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 1rem 0; }
      .filtro { border: 2px solid var(--cima-verde); background: #fff; color: var(--cima-verde-oscuro); border-radius: 999px; padding: 0 1rem; font-size: 1rem; font-weight: 600; cursor: pointer; }
      .filtro--activo { background: var(--cima-verde); color: #fff; }
      .lista { list-style: none; margin: 0; padding: 0; display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
      .tarjeta { background: var(--cima-superficie); border: 1px solid var(--cima-borde); border-radius: var(--cima-radio); padding: 1.25rem; display: flex; flex-direction: column; gap: 0.5rem; }
      .tarjeta--lista { border-color: var(--cima-verde); background: var(--cima-verde-claro); }
      .tarjeta__tema { font-weight: 700; color: var(--cima-verde-oscuro); font-size: 0.95rem; }
      .tarjeta__titulo { margin: 0; font-size: 1.2rem; }
      .tarjeta__texto, .tarjeta__meta, .tarjeta__estado { margin: 0; color: var(--cima-texto-suave); }
      .tarjeta__estado { font-weight: 700; color: var(--cima-texto); }
      .tarjeta .sb-ui-button { margin-top: auto; text-align: center; display: inline-flex; align-items: center; justify-content: center; text-decoration: none; }
    `,
  ],
})
export class LearningPageComponent {
  private readonly learning = inject(LearningService);
  private readonly gamificacion = inject(GamificationService);

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly rutas = signal<readonly Ruta[]>([]);
  readonly aviso = signal<string | null>(null);
  readonly filtro = signal<string>('');
  readonly resumen = this.gamificacion.resumen;

  readonly tarjetas = computed<readonly TarjetaCapsula[]>(() =>
    this.rutas().flatMap((r) =>
      r.items.map((i) => ({
        pathId: r.path_id,
        rutaTitulo: r.title ?? 'Ruta de aprendizaje',
        estado: i.status,
        capsula: i.capsule,
      })),
    ),
  );
  readonly temas = computed<readonly string[]>(() => [
    ...new Set(this.tarjetas().map((t) => t.capsula.topic)),
  ]);
  readonly visibles = computed<readonly TarjetaCapsula[]>(() =>
    this.tarjetas().filter((t) => this.filtro() === '' || t.capsula.topic === this.filtro()),
  );
  readonly total = computed(() => this.tarjetas().length);
  readonly completadas = computed(
    () => this.tarjetas().filter((t) => t.estado === 'completed').length,
  );
  readonly porcentaje = computed(() =>
    this.total() === 0 ? 0 : Math.round((this.completadas() / this.total()) * 100),
  );

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      const [rutas, seleccion] = await Promise.all([
        this.learning.obtenerRutas(),
        this.learning.obtenerMicrocapsulas(),
        this.gamificacion.cargarResumen(),
      ]);
      this.rutas.set(rutas);
      this.aviso.set(seleccion.notice);
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

  textoEstado(estado: EstadoCapsula): string {
    if (estado === 'completed') {
      return 'Completada';
    }
    return estado === 'next' ? 'Te toca ahora' : 'Pendiente';
  }
}
