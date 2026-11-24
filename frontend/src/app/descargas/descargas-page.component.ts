import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { NetworkStatusService } from '../core/network-status.service';
import { Descarga, formatoMegas } from './descargas';
import { DescargasService } from './descargas.service';

/**
 * Mis descargas: los videos guardados en el celular para verlos sin conexión
 * (Req 18.1). Se pueden ver aquí mismo, aun sin internet y sin sesión, porque
 * solo lee lo que está en el dispositivo; y borrar uno a uno o todos. Las
 * descargas no se borran al cerrar sesión: las borra la persona.
 */
@Component({
  selector: 'cima-descargas-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="descargas">
      <h1 class="titulo">Mis descargas</h1>

      @if (!servicio.disponible) {
        <div class="sb-ui-alert sb-ui-alert--info" role="status">
          Este navegador no permite descargar videos. Puede verlos en las lecciones cuando tenga internet.
        </div>
      } @else if (servicio.lista().length === 0) {
        <p class="texto">
          Todavía no tiene videos descargados. En las lecciones con video verá el botón
          "Descargar para ver sin conexión".
        </p>
        <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton" routerLink="/mi-ruta">Ir a mi ruta</a>
      } @else {
        <p class="texto">
          Ocupan {{ megas(servicio.bytesUsados()) }} en su celular.
          @if (libre(); as l) {
            Quedan unos {{ megas(l) }} libres para descargas.
          }
        </p>

        <ul class="lista">
          @for (d of servicio.lista(); track d.url) {
            <li class="descarga">
              <h2 class="descarga__titulo">{{ d.leccion }}</h2>
              <p class="descarga__meta">{{ megas(d.bytes) }} · descargado el {{ fecha(d.fecha) }}</p>

              @if (viendo() === d.url && fuente(); as src) {
                <video class="video" [src]="src" controls autoplay playsinline
                       [attr.aria-label]="'Video: ' + d.titulo" (ended)="alTerminar(d)"></video>
              }

              <label class="opcion">
                <input type="checkbox" [checked]="d.borrarAlTerminar"
                       (change)="servicio.cambiarBorrarAlTerminar(d.url, $any($event.target).checked)" />
                Borrarlo cuando lo termine de ver
              </label>
              <div class="acciones">
                @if (viendo() === d.url) {
                  <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton"
                          (click)="cerrar()">Cerrar el video</button>
                } @else {
                  <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill boton"
                          (click)="ver(d)">Ver aquí</button>
                }
                <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton"
                        (click)="borrar(d)">Borrar</button>
              </div>
              @if (red.online()) {
                <a class="enlace" [routerLink]="['/aprendizaje/leccion', d.rutaId, d.capsulaId]">Ir a la lección</a>
              }
            </li>
          }
        </ul>

        @if (confirmando()) {
          <div class="sb-ui-alert sb-ui-alert--warning confirmar" role="alert">
            <p>¿Seguro que quiere borrar todos los videos descargados?</p>
            <div class="acciones">
              <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill boton"
                      (click)="borrarTodas()">Sí, borrar todos</button>
              <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton"
                      (click)="confirmando.set(false)">No, dejarlos</button>
            </div>
          </div>
        } @else {
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton"
                  (click)="confirmando.set(true)">Borrar todas las descargas</button>
        }
      }

      @if (mensaje(); as m) {
        <div class="sb-ui-alert sb-ui-alert--info" role="status">{{ m }}</div>
      }
    </section>
  `,
  styles: [
    `
      .descargas { padding: 1rem; max-width: 680px; margin: 0 auto; font-size: 1.1rem; }
      .titulo { font-size: 1.5rem; }
      .texto { color: var(--cima-texto); line-height: 1.5; }
      .lista { list-style: none; margin: 0 0 1rem; padding: 0; display: grid; gap: 1rem; }
      .descarga { background: var(--cima-superficie); border: 1px solid var(--cima-borde); border-radius: var(--cima-radio); padding: 1.25rem; }
      .descarga__titulo { margin: 0; font-size: 1.15rem; color: var(--cima-verde-oscuro); }
      .descarga__meta { margin: 0.25rem 0 0.75rem; color: var(--cima-texto-suave); }
      .video { width: 100%; max-height: 60vh; background: #000; display: block; border-radius: var(--cima-radio); margin-bottom: 0.75rem; }
      .opcion { display: flex; align-items: center; gap: 0.75rem; min-height: 44px; margin-bottom: 0.5rem; }
      .opcion input { width: 1.5rem; height: 1.5rem; flex: none; }
      .acciones { display: flex; flex-wrap: wrap; gap: 0.75rem; }
      .boton { display: flex; align-items: center; justify-content: center; flex: 1 1 10rem; text-decoration: none; }
      .enlace { display: inline-flex; align-items: center; min-height: 44px; margin-top: 0.5rem; color: var(--cima-verde-oscuro); font-weight: 700; }
      .confirmar p { margin: 0 0 0.75rem; }
    `,
  ],
})
export class DescargasPageComponent {
  protected readonly servicio = inject(DescargasService);
  protected readonly red = inject(NetworkStatusService);

  /** Video que se está viendo en esta pantalla y su dirección local (`blob:`). */
  protected readonly viendo = signal<string | null>(null);
  protected readonly fuente = signal<string | null>(null);
  protected readonly libre = signal<number | null>(null);
  protected readonly confirmando = signal<boolean>(false);
  protected readonly mensaje = signal<string | null>(null);

  constructor() {
    void this.servicio.recargar();
    void this.servicio.espacioLibre().then((l) => this.libre.set(l));
    inject(DestroyRef).onDestroy(() => this.liberar());
  }

  protected megas(bytes: number): string {
    return formatoMegas(bytes);
  }

  protected fecha(iso: string): string {
    const d = new Date(iso);
    return Number.isNaN(d.getTime())
      ? ''
      : d.toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  protected async ver(d: Descarga): Promise<void> {
    this.cerrar();
    this.mensaje.set(null);
    const local = await this.servicio.urlLocal(d.url);
    if (!local) {
      this.mensaje.set('No encontramos este video en su celular. Descárguelo de nuevo desde la lección.');
      await this.servicio.borrar(d.url);
      return;
    }
    this.viendo.set(d.url);
    this.fuente.set(local);
  }

  protected cerrar(): void {
    this.liberar();
    this.viendo.set(null);
  }

  protected async borrar(d: Descarga): Promise<void> {
    if (this.viendo() === d.url) {
      this.cerrar();
    }
    await this.servicio.borrar(d.url);
    this.mensaje.set('Borramos el video de su celular.');
  }

  protected async alTerminar(d: Descarga): Promise<void> {
    if (d.borrarAlTerminar) {
      this.cerrar();
      await this.servicio.borrar(d.url);
      this.mensaje.set('Borramos el video de su celular porque ya lo terminó de ver.');
    }
  }

  protected async borrarTodas(): Promise<void> {
    this.cerrar();
    await this.servicio.borrarTodas();
    this.confirmando.set(false);
    this.mensaje.set('Borramos todos los videos de su celular.');
  }

  private liberar(): void {
    const actual = this.fuente();
    if (actual) {
      URL.revokeObjectURL(actual);
      this.fuente.set(null);
    }
  }
}
