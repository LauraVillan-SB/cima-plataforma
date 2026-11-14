import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GamificationService } from '../gamificacion/gamification.service';
import {
  ItemRuta,
  LearningService,
  ResultadoFinalizacion,
  Ruta,
  VideoArchivo,
} from './learning.service';
import { etiquetaTema, minutos } from './temas';

/** Tope de tiempo reportado, igual al del backend (24 h). */
const MAX_ELAPSED_SEC = 86400;

/** Video propio: solo la dirección relativa del backend, igual al patrón del servidor. */
const PATRON_ARCHIVO = /^\/api\/v1\/aprendizaje\/medios\/[a-z0-9][a-z0-9-]{0,62}\.mp4$/;

/** Solo se incrustan videos de YouTube por HTTPS con identificador de 11 caracteres. */
const PATRON_EMBED = /^https:\/\/www\.youtube(-nocookie)?\.com\/embed\/[A-Za-z0-9_-]{11}$/;

/**
 * Lección de una microcápsula: lee el contenido, marca como terminada y
 * muestra la celebración con el avance real. Los puntos e insignias los
 * otorga el backend al completar la ruta; el cliente nunca los asigna
 * (Req 19.3). El video es complementario y opcional.
 */
@Component({
  selector: 'cima-lesson-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="leccion">
      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando la lección...</p>
      } @else if (error() || !item()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar esta lección. Vuelve a las microcápsulas e intenta de nuevo.
        </div>
        <a routerLink="/aprendizaje" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill enlace">Volver</a>
      } @else if (resultado(); as r) {
        <div class="celebra" role="status" aria-live="polite">
          <h1 class="celebra__titulo">¡Muy bien! Terminaste la lección</h1>
          <p>Llevas {{ r.completed_count }} de {{ r.total_count }} microcápsulas de esta ruta.</p>
          @if (r.path_completed) {
            <p>¡Completaste la ruta! Ya puedes presentar la evaluación.</p>
            <a [routerLink]="['/evaluacion', r.path_id]" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill enlace">Presentar evaluación</a>
          }
          <a routerLink="/aprendizaje" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill enlace">Volver a las microcápsulas</a>
        </div>
      } @else if (item(); as i) {
        <span class="tema">{{ etiqueta(i.capsule.topic) }} · {{ mins(i.capsule.duration_sec) }} min</span>
        <h1 class="titulo">{{ i.capsule.title ?? etiqueta(i.capsule.topic) }}</h1>
        @for (p of i.capsule.paragraphs; track $index) {
          <p class="parrafo">{{ p }}</p>
        }
        @if (videoArchivo(); as v) {
          <video class="video video--archivo" [src]="v.url" controls preload="none" playsinline
                 [attr.aria-label]="'Video: ' + v.title"></video>
        }
        @if (videoUrl(); as url) {
          <iframe class="video" [src]="url" title="Video complementario"
                  loading="lazy" referrerpolicy="strict-origin-when-cross-origin"
                  allowfullscreen></iframe>
        }
        @if (i.capsule.key_points.length > 0) {
          <section class="puntos" aria-labelledby="puntos-titulo">
            <h2 id="puntos-titulo">Lo más importante</h2>
            <ul>
              @for (k of i.capsule.key_points; track $index) {
                <li>{{ k }}</li>
              }
            </ul>
          </section>
        }
        @if (i.status === 'pending') {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">
            Completa primero la microcápsula anterior de esta ruta.
          </div>
        } @else if (i.status === 'next') {
          <button type="button" class="sb-ui-button sb-ui-button--primary sb-ui-button--fill enlace"
                  [disabled]="enviando()" (click)="terminar(i)">
            {{ enviando() ? 'Guardando...' : 'Terminé la lección' }}
          </button>
          @if (errorEnvio()) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">
              No pudimos guardar tu avance. Intenta de nuevo.
            </div>
          }
        }
        <a routerLink="/aprendizaje" class="volver">Volver a las microcápsulas</a>
      }
    </article>
  `,
  styles: [
    `
      .leccion { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.125rem; line-height: 1.6; }
      .tema { font-weight: 700; color: var(--cima-verde-oscuro); }
      .titulo { margin: 0.25rem 0 1rem; font-size: 1.6rem; }
      .parrafo { margin: 0 0 1rem; }
      .video { width: 100%; aspect-ratio: 16 / 9; border: 0; border-radius: var(--cima-radio); margin-bottom: 1rem; }
      .video--archivo { aspect-ratio: auto; max-height: 70vh; background: #000; display: block; }
      .puntos { background: var(--cima-verde-claro); border-left: 6px solid var(--cima-verde); border-radius: 8px; padding: 0.5rem 1rem; margin-bottom: 1.5rem; }
      .enlace { display: inline-flex; align-items: center; justify-content: center; width: 100%; margin: 0.5rem 0; text-decoration: none; }
      .volver { display: inline-flex; align-items: center; color: var(--cima-verde-oscuro); font-weight: 600; }
      .celebra { text-align: center; background: var(--cima-verde-oscuro); color: #fff; border-radius: var(--cima-radio); padding: 1.5rem; }
      .celebra__titulo { color: var(--cima-dorado); }
    `,
  ],
})
export class LessonPageComponent {
  private readonly learning = inject(LearningService);
  private readonly gamificacion = inject(GamificationService);
  private readonly route = inject(ActivatedRoute);
  private readonly sanitizer = inject(DomSanitizer);

  private readonly pathId = this.route.snapshot.paramMap.get('pathId') ?? '';
  private readonly capsuleId = this.route.snapshot.paramMap.get('capsuleId') ?? '';
  private readonly inicio = Date.now();

  readonly cargando = signal<boolean>(true);
  readonly error = signal<boolean>(false);
  readonly errorEnvio = signal<boolean>(false);
  readonly enviando = signal<boolean>(false);
  readonly ruta = signal<Ruta | null>(null);
  readonly resultado = signal<ResultadoFinalizacion | null>(null);

  readonly item = computed<ItemRuta | null>(
    () => this.ruta()?.items.find((i) => i.capsule.id === this.capsuleId) ?? null,
  );
  /** Video propio; solo si la dirección es la del backend (relativa y con el prefijo fijo). */
  readonly videoArchivo = computed<VideoArchivo | null>(() => {
    const video = this.item()?.capsule.video_file ?? null;
    return video && PATRON_ARCHIVO.test(video.url) ? video : null;
  });
  readonly videoUrl = computed<SafeResourceUrl | null>(() => {
    const url = this.item()?.capsule.video?.embed_url ?? '';
    return PATRON_EMBED.test(url) ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  });

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    try {
      const rutas = await this.learning.obtenerRutas();
      this.ruta.set(rutas.find((r) => r.path_id === this.pathId) ?? null);
    } catch {
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  /** Registra la finalización; el id de evento se genera aquí para ser idempotente. */
  async terminar(item: ItemRuta): Promise<void> {
    this.enviando.set(true);
    this.errorEnvio.set(false);
    const segundos = Math.min(MAX_ELAPSED_SEC, Math.round((Date.now() - this.inicio) / 1000));
    try {
      this.resultado.set(
        await this.learning.finalizar(item.capsule.id, this.pathId, crypto.randomUUID(), segundos),
      );
    } catch {
      this.errorEnvio.set(true);
      return;
    } finally {
      this.enviando.set(false);
    }
    await this.refrescarChips();
  }

  /** Actualiza puntos y racha del encabezado; si falla, el avance ya quedó guardado. */
  private async refrescarChips(): Promise<void> {
    try {
      await this.gamificacion.cargarResumen();
    } catch {
      // Los chips se actualizarán en la siguiente carga; no afecta el avance guardado.
    }
  }

  etiqueta(topic: string): string {
    return etiquetaTema(topic);
  }

  mins(segundos: number): number {
    return minutos(segundos);
  }
}
