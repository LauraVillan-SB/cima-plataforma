import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { NetworkStatusService } from '../core/network-status.service';
import { formatoMegas } from './descargas';
import { DescargasService, ErrorDescarga, MotivoFalla } from './descargas.service';

const MENSAJES_FALLA: Readonly<Record<MotivoFalla, string>> = {
  sin_soporte: 'Este navegador no permite descargar videos. Puedes verlo con internet.',
  no_permitido: 'Este video no se puede descargar.',
  espacio: 'No hay espacio suficiente en tu celular. Borra alguna descarga e intenta de nuevo.',
  red: 'Se cortó la descarga. Revisa tu conexión e intenta de nuevo.',
};

/**
 * Video propio de una lección con la opción de descargarlo para verlo sin
 * conexión (Req 18.1). Si está descargado se reproduce desde el celular, aunque
 * haya internet, para no gastar datos. Sin conexión y sin descarga avisa que el
 * video necesita internet; la lección se puede leer igual.
 */
@Component({
  selector: 'cima-video-propio',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="video-propio">
      @if (fuente(); as src) {
        <video class="video" [src]="src" controls preload="metadata" playsinline
               [attr.aria-label]="'Video: ' + titulo()" (ended)="alTerminar()"></video>
      } @else if (!red.online()) {
        <div class="sb-ui-alert sb-ui-alert--info" role="status">
          Este video necesita internet porque no lo has descargado. Puedes leer la lección sin conexión.
        </div>
      }

      @if (descargas.disponible) {
        @if (descarga(); as d) {
          <p class="estado">
            <span aria-hidden="true">✓</span> Guardado en este celular · {{ megas(d.bytes) }}
          </p>
          <label class="opcion">
            <input type="checkbox" [checked]="d.borrarAlTerminar"
                   (change)="cambiarBorrar($any($event.target).checked)" />
            Borrarlo cuando lo termine de ver
          </label>
          <div class="acciones">
            <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton"
                    (click)="borrar()">Borrar descarga</button>
            <a class="enlace" routerLink="/descargas">Mis descargas</a>
          </div>
        } @else if (avance() !== null) {
          <p class="estado" role="status" aria-live="polite">Descargando... {{ avance() }} %</p>
          <div class="barra" role="progressbar" aria-label="Avance de la descarga"
               [attr.aria-valuenow]="avance()" aria-valuemin="0" aria-valuemax="100">
            <div class="barra__relleno" [style.width.%]="avance()"></div>
          </div>
        } @else if (red.online()) {
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill boton"
                  (click)="descargar()">
            Descargar para ver sin conexión{{ tamano() ? ' (' + megas(tamano()!) + ')' : '' }}
          </button>
          <label class="opcion">
            <input type="checkbox" [checked]="borrarAlTerminar()"
                   (change)="borrarAlTerminar.set($any($event.target).checked)" />
            Borrarlo cuando lo termine de ver
          </label>
        }
        @if (mensaje(); as m) {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">{{ m }}</div>
        }
        @if (error(); as e) {
          <div class="sb-ui-alert sb-ui-alert--error" role="alert">{{ e }}</div>
        }
      }
    </div>
  `,
  styles: [
    `
      .video-propio { margin-bottom: 1rem; }
      .video { width: 100%; max-height: 70vh; background: #000; display: block; border-radius: var(--cima-radio); margin-bottom: 0.75rem; }
      .estado { margin: 0 0 0.5rem; font-weight: 700; color: var(--cima-verde-oscuro); }
      .opcion { display: flex; align-items: center; gap: 0.75rem; min-height: 44px; margin-bottom: 0.5rem; }
      .opcion input { width: 1.5rem; height: 1.5rem; flex: none; }
      .acciones { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; }
      .boton { display: flex; align-items: center; justify-content: center; width: 100%; margin-bottom: 0.5rem; }
      .acciones .boton { width: auto; flex: 1 1 12rem; margin-bottom: 0; }
      .enlace { display: inline-flex; align-items: center; min-height: 44px; color: var(--cima-verde-oscuro); font-weight: 700; }
      .barra { background: var(--cima-verde-claro); border-radius: 999px; height: 12px; overflow: hidden; margin-bottom: 0.75rem; }
      .barra__relleno { background: var(--cima-verde); height: 100%; }
    `,
  ],
})
export class VideoPropioComponent {
  protected readonly descargas = inject(DescargasService);
  protected readonly red = inject(NetworkStatusService);

  /** Dirección del video en el backend (ya validada por la lección). */
  readonly url = input.required<string>();
  readonly titulo = input.required<string>();
  readonly leccion = input.required<string>();
  readonly rutaId = input.required<string>();
  readonly capsulaId = input.required<string>();

  protected readonly tamano = signal<number | null>(null);
  protected readonly borrarAlTerminar = signal<boolean>(false);
  protected readonly error = signal<string | null>(null);
  protected readonly mensaje = signal<string | null>(null);
  /** Dirección local (`blob:`) del video descargado mientras se muestra. */
  private readonly urlLocal = signal<string | null>(null);

  protected readonly descarga = computed(() => this.descargas.lista().find((d) => d.url === this.url()));
  /** Solo cambia al descargar o borrar; no al cambiar "borrar al terminar". */
  private readonly descargado = computed(() => !!this.descarga());
  protected readonly avance = computed(() => {
    const valor = this.descargas.progreso().get(this.url());
    return valor === undefined ? null : Math.round(valor * 100);
  });

  /** Lo descargado se ve desde el celular; si no, desde el backend cuando hay red. */
  protected readonly fuente = computed(() => {
    if (this.descargado()) {
      return this.urlLocal();
    }
    return this.red.online() ? this.url() : null;
  });

  constructor() {
    // Prepara la dirección local al descargar y la libera al borrar.
    effect(() => {
      const descargado = this.descargado();
      const url = this.url();
      untracked(() => void this.prepararLocal(descargado, url));
    });
    // Consulta el tamaño para mostrarlo en el botón antes de descargar.
    effect(() => {
      if (this.red.online() && !this.descargado() && this.tamano() === null) {
        const url = this.url();
        untracked(() => void this.descargas.tamano(url).then((t) => this.tamano.set(t)));
      }
    });
    inject(DestroyRef).onDestroy(() => this.liberarLocal());
  }

  protected megas(bytes: number): string {
    return formatoMegas(bytes);
  }

  protected async descargar(): Promise<void> {
    this.error.set(null);
    this.mensaje.set(null);
    try {
      await this.descargas.descargar(
        {
          url: this.url(),
          titulo: this.titulo(),
          leccion: this.leccion(),
          rutaId: this.rutaId(),
          capsulaId: this.capsulaId(),
        },
        this.borrarAlTerminar(),
      );
      this.mensaje.set('Listo. Ya puedes ver este video sin internet.');
    } catch (error) {
      if (error instanceof ErrorDescarga) {
        this.error.set(MENSAJES_FALLA[error.motivo]);
        return;
      }
      throw error;
    }
  }

  protected async cambiarBorrar(valor: boolean): Promise<void> {
    await this.descargas.cambiarBorrarAlTerminar(this.url(), valor);
  }

  protected async borrar(): Promise<void> {
    await this.descargas.borrar(this.url());
    this.mensaje.set('Borramos el video de tu celular.');
  }

  /** Si la persona lo pidió, borra la descarga apenas termina de ver el video. */
  protected async alTerminar(): Promise<void> {
    if (this.descarga()?.borrarAlTerminar) {
      await this.descargas.borrar(this.url());
      this.mensaje.set('Borramos el video de tu celular porque ya lo terminaste de ver.');
    }
  }

  private async prepararLocal(descargado: boolean, url: string): Promise<void> {
    this.liberarLocal();
    if (descargado) {
      this.urlLocal.set(await this.descargas.urlLocal(url));
    }
  }

  private liberarLocal(): void {
    const actual = this.urlLocal();
    if (actual) {
      URL.revokeObjectURL(actual);
      this.urlLocal.set(null);
    }
  }
}
