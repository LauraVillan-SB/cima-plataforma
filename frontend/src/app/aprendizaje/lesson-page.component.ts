import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { NetworkStatusService } from '../core/network-status.service';
import { VideoPropioComponent } from '../descargas/video-propio.component';
import { GamificationService } from '../gamificacion/gamification.service';
import {
  ItemRuta,
  LearningService,
  ResultadoFinalizacion,
  Ruta,
  VideoArchivo,
} from './learning.service';
import { RUTA_TECNOLOGIA_ID, SigaAprendiendoComponent } from './siga-aprendiendo.component';
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
  imports: [RouterLink, VideoPropioComponent, SigaAprendiendoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="leccion">
      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando la lección...</p>
      } @else if (error() || !item()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar esta lección. Vuelva a su ruta e intente de nuevo.
        </div>
        <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke enlace">Volver a mi ruta</a>
      } @else if (resultado(); as r) {
        <div class="celebra" role="status" aria-live="polite">
          <h1 class="celebra__titulo">¡Muy bien! Terminó la lección</h1>
          <p>Lleva {{ r.completed_count }} de {{ r.total_count }} microcápsulas de esta ruta.</p>
          @if (r.path_completed) {
            <p>¡Completó la ruta! Ya puede presentar la evaluación.</p>
            <a [routerLink]="['/evaluacion', r.path_id]" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill enlace">Presentar evaluación</a>
            <a [routerLink]="['/encuesta', r.path_id]" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill enlace">Cuéntenos qué le pareció (opcional)</a>
          }
          <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill enlace">Volver a mi ruta</a>
        </div>
      } @else if (item(); as i) {
        <span class="tema">{{ etiqueta(i.capsule.topic) }} · {{ mins(i.capsule.duration_sec) }} min</span>
        <h1 class="titulo">{{ i.capsule.title ?? etiqueta(i.capsule.topic) }}</h1>
        @if (videoArchivo(); as v) {
          <cima-video-propio [url]="v.url" [titulo]="v.title"
                             [leccion]="i.capsule.title ?? etiqueta(i.capsule.topic)"
                             [rutaId]="ruta()?.path_id ?? ''" [capsulaId]="i.capsule.id" />
        }
        @if (videoUrl(); as url) {
          @if (red.online()) {
            <iframe class="video" [src]="url" title="Video complementario"
                    loading="lazy" referrerpolicy="strict-origin-when-cross-origin"
                    allowfullscreen></iframe>
          } @else {
            <!-- YouTube no permite guardar sus videos; sin conexión se avisa y la lección se lee igual. -->
            <div class="sb-ui-alert sb-ui-alert--info" role="status">
              Este video es de YouTube y necesita internet. Puede leer la lección sin conexión.
            </div>
          }
        }
        <!-- Acordeón nativo (details/summary): accesible por teclado y sin JavaScript extra. -->
        <details class="acordeon" open>
          <summary class="acordeon__titulo">Lea la lección</summary>
          <div class="acordeon__contenido">
            @for (p of i.capsule.paragraphs; track $index) {
              <p class="parrafo">{{ p }}</p>
            }
          </div>
        </details>
        @if (i.capsule.key_points.length > 0) {
          <details class="acordeon">
            <summary class="acordeon__titulo">Lo más importante</summary>
            <div class="acordeon__contenido">
              <ul>
                @for (k of i.capsule.key_points; track $index) {
                  <li>{{ k }}</li>
                }
              </ul>
            </div>
          </details>
        }
        @if (esRutaTecnologia()) {
          <cima-siga-aprendiendo />
        }
        @if (i.status === 'pending') {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">
            Complete primero la microcápsula anterior de esta ruta.
          </div>
        } @else if (i.status === 'next') {
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke enlace"
                  [disabled]="enviando()" (click)="terminar(i)">
            {{ enviando() ? 'Guardando...' : 'Terminé la lección' }}
          </button>
          @if (errorEnvio()) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">
              No pudimos guardar su avance. Intente de nuevo.
            </div>
          }
        }
        <a routerLink="/mi-ruta" class="volver">Volver a mi ruta</a>
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
      .acordeon { border: 1px solid var(--cima-verde); border-radius: var(--cima-radio); margin-bottom: 1rem; overflow: hidden; }
      .acordeon__titulo { cursor: pointer; padding: 0.75rem 1rem; min-height: 44px; font-weight: 700; color: var(--cima-verde-oscuro); background: var(--cima-verde-claro); }
      .acordeon__contenido { padding: 1rem 1rem 0; }
      .acordeon__contenido ul { margin-top: 0; }
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
  protected readonly red = inject(NetworkStatusService);

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
  /** Las lecciones de la ruta de tecnología muestran "Siga aprendiendo" con enlaces oficiales. */
  readonly esRutaTecnologia = computed<boolean>(() => this.ruta()?.path_id === RUTA_TECNOLOGIA_ID);
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
