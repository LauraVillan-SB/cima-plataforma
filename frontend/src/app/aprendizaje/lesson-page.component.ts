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
import { abrirTextoDeEntrada } from './leccion';
import { etiquetaTema, iconoTema, minutos } from './temas';

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
  imports: [RouterLink, VideoPropioComponent],
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
        <p class="meta">
          <span class="meta__dato">
            <i class="fa-solid {{ icono(i.capsule.topic) }}" aria-hidden="true"></i>
            {{ etiqueta(i.capsule.topic) }}
          </span>
          <span class="meta__dato">
            <i class="fa-solid fa-clock" aria-hidden="true"></i>
            {{ mins(i.capsule.duration_sec) }} min
          </span>
          @if (videoArchivo() || videoUrl()) {
            <span class="meta__dato">
              <i class="fa-solid fa-circle-play" aria-hidden="true"></i>
              Con video
            </span>
          }
        </p>
        <h1 class="titulo">{{ i.capsule.title ?? etiqueta(i.capsule.topic) }}</h1>
        <!-- El video va primero: es lo más fácil de seguir; el texto completo queda en el acordeón. -->
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
        @if (i.capsule.summary) {
          <p class="resumen">{{ i.capsule.summary }}</p>
        }
        @if (i.capsule.key_points.length > 0) {
          <section class="puntos" aria-labelledby="puntos-titulo">
            <h2 id="puntos-titulo" class="puntos__titulo">
              <i class="fa-solid fa-lightbulb" aria-hidden="true"></i>
              Lo más importante
            </h2>
            <ul class="puntos__lista">
              @for (k of i.capsule.key_points; track $index) {
                <li class="puntos__item">
                  <i class="fa-solid fa-circle-check puntos__icono" aria-hidden="true"></i>
                  <span>{{ k }}</span>
                </li>
              }
            </ul>
          </section>
        }
        @if (i.capsule.paragraphs.length > 0) {
          <!-- Acordeón del sistema de diseño (details/summary nativo: accesible y sin JS).
               Arranca cerrado; se abre de entrada solo si no hay nada más que leer arriba. -->
          <details class="sb-ui-accordion sb-ui-accordion--primary sb-ui-accordion--no-action mas"
                   [open]="textoAbierto()">
            <summary class="sb-ui-accordion__header">
              <span class="sb-ui-accordion__icon-start"><i class="fa-solid fa-book-open" aria-hidden="true"></i></span>
              <span class="sb-ui-accordion__label">¿Quiere conocer más?</span>
              <span class="sb-ui-accordion__icon-end"><i class="fa-solid fa-chevron-down" aria-hidden="true"></i></span>
            </summary>
            <div class="sb-ui-accordion__content">
              @for (p of i.capsule.paragraphs; track $index) {
                <p class="parrafo">{{ p }}</p>
              }
            </div>
          </details>
        }
        @if (i.status === 'pending') {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">
            Complete primero la microcápsula anterior de esta ruta.
          </div>
        } @else if (i.status === 'next') {
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke enlace"
                  [disabled]="enviando()" (click)="terminar(i)">
            <i class="fa-solid fa-check icono-boton" aria-hidden="true"></i>
            {{ enviando() ? 'Guardando...' : 'Terminé la lección' }}
          </button>
          @if (errorEnvio()) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">
              No pudimos guardar su avance. Intente de nuevo.
            </div>
          }
        }
        <a routerLink="/mi-ruta" class="volver">
          <i class="fa-solid fa-arrow-left icono-boton" aria-hidden="true"></i>
          Volver a mi ruta
        </a>
      }
    </article>
  `,
  styles: [
    `
      .leccion { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.125rem; line-height: 1.6; }
      .meta { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; margin: 0; font-weight: 700; color: var(--cima-verde-oscuro); }
      .meta__dato { display: inline-flex; align-items: center; gap: 0.4rem; }
      .titulo { margin: 0.25rem 0 1rem; font-size: 1.6rem; line-height: 1.25; }
      /* Texto menos denso: línea más corta, más interlineado y más espacio entre párrafos. */
      .resumen { margin: 0 0 1.25rem; font-size: 1.2rem; max-width: 60ch; }
      /* Dentro del acordeón el sistema de diseño usa 18 px y gris claro (#757575); el
         texto de la lección se lee con el tamaño y el color oscuro del resto (Req 13.2). */
      .parrafo { margin: 0 0 1.25rem; max-width: 60ch; line-height: 1.75; font-size: 1.125rem; color: var(--cima-texto); }
      .mas { display: block; margin-bottom: 1.5rem; }
      .icono-boton { margin-right: 0.5rem; }
      .video { width: 100%; aspect-ratio: 16 / 9; border: 0; border-radius: var(--cima-radio); margin-bottom: 1rem; }
      .video--archivo { aspect-ratio: auto; max-height: 70vh; background: #000; display: block; }
      .puntos { background: var(--cima-verde-claro); border-left: 6px solid var(--cima-verde); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1.5rem; }
      .puntos__titulo { display: flex; align-items: center; gap: 0.5rem; margin: 0 0 0.75rem; font-size: 1.25rem; color: var(--cima-verde-oscuro); }
      .puntos__lista { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.75rem; }
      .puntos__item { display: flex; align-items: flex-start; gap: 0.6rem; }
      .puntos__icono { flex: none; margin-top: 0.3rem; color: var(--cima-verde-oscuro); }
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
  /** Video propio; solo si la dirección es la del backend (relativa y con el prefijo fijo). */
  readonly videoArchivo = computed<VideoArchivo | null>(() => {
    const video = this.item()?.capsule.video_file ?? null;
    return video && PATRON_ARCHIVO.test(video.url) ? video : null;
  });
  readonly videoUrl = computed<SafeResourceUrl | null>(() => {
    const url = this.item()?.capsule.video?.embed_url ?? '';
    return PATRON_EMBED.test(url) ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  });

  /** Si el texto completo arranca abierto: solo cuando no hay nada más que leer arriba. */
  readonly textoAbierto = computed<boolean>(() => {
    const capsula = this.item()?.capsule;
    return abrirTextoDeEntrada({
      tieneVideo: this.videoArchivo() !== null || this.videoUrl() !== null,
      resumen: capsula?.summary,
      puntosClave: capsula?.key_points ?? [],
    });
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

  icono(topic: string): string {
    return iconoTema(topic);
  }
}
