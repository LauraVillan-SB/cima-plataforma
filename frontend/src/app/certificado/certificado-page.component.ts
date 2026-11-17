import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  MENSAJE_NO_ENCONTRADO,
  codigoLegible,
  fechaCertificado,
  finalCelular,
  mensajeError,
} from './certificado';
import { Certificado, CertificationService } from './certification.service';

/** Identificador de ruta con forma de UUID; si no la tiene no se llama al backend. */
const PATRON_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Certificado de una ruta aprobada (Req 6.1, 6.3, 6.5).
 *
 * Al entrar pide el Certificado al backend, que lo emite si la ruta está completa y la
 * evaluación aprobada, o devuelve el que ya existía (idempotente). Muestra el nombre de
 * la ruta, el celular enmascarado del titular, la fecha y el código verificable, y
 * permite imprimirlo o guardarlo en PDF con el menú del celular. Si aún no se puede
 * emitir, muestra el mensaje del backend (Req 6.2). No guarda nada en el celular.
 */
@Component({
  selector: 'cima-certificado-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pagina">
      @if (cargando()) {
        <p role="status" aria-live="polite">Preparando tu certificado...</p>
      } @else if (error(); as mensaje) {
        <div class="sb-ui-alert sb-ui-alert--warning" role="alert">{{ mensaje }}</div>
        <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large enlace">
          Ir a mi ruta
        </a>
      } @else if (certificado(); as c) {
        <article class="certificado" aria-labelledby="titulo-certificado">
          <img class="certificado__logo" src="logos/sb-logo-horizontal.svg" alt="Seguros Bolívar" width="180" height="48" />
          <p class="certificado__escuela">Escuela de Sostenibilidad e Inclusión · CIMA</p>
          <h1 id="titulo-certificado" class="certificado__titulo">Certificado de aprendizaje</h1>
          <p class="certificado__texto">Se certifica que la persona con celular terminado en</p>
          <p class="certificado__dato">{{ celular() || '****' }}</p>
          <p class="certificado__texto">completó y aprobó la ruta</p>
          <h2 class="certificado__ruta">{{ c.path_title ?? 'Ruta de aprendizaje de CIMA' }}</h2>
          @if (fecha()) {
            <p class="certificado__texto">el {{ fecha() }}.</p>
          }
          <div class="certificado__codigo">
            <span class="certificado__codigo-etiqueta">Código de verificación</span>
            <span class="certificado__codigo-valor" [attr.aria-label]="'Código ' + c.verification_code">{{ codigo() }}</span>
          </div>
          <p class="certificado__nota">
            Este certificado acredita lo que aprendiste en CIMA. No es una póliza ni un
            producto de seguros.
          </p>
        </article>
        <div class="acciones" data-no-leer>
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large" (click)="imprimir()">
            Imprimir o guardar en PDF
          </button>
          <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large enlace">
            Volver a mi ruta
          </a>
        </div>
      }
    </section>
  `,
  styles: [
    `
      .pagina { padding: 1.5rem 1rem; max-width: 640px; margin: 0 auto; }
      .certificado {
        background: #fff;
        border: 6px double var(--cima-verde-oscuro);
        border-radius: var(--cima-radio);
        padding: 2rem 1.25rem;
        text-align: center;
        color: var(--cima-texto);
      }
      .certificado__logo { height: 40px; width: auto; }
      .certificado__escuela { margin: 0.75rem 0 0; color: var(--cima-texto-suave); font-weight: 600; }
      .certificado__titulo { margin: 0.75rem 0 1.25rem; font-size: 1.75rem; color: var(--cima-verde-oscuro); }
      .certificado__texto { margin: 0.25rem 0; }
      .certificado__dato { margin: 0.25rem 0 0.75rem; font-size: 1.5rem; font-weight: 700; letter-spacing: 0.1em; }
      .certificado__ruta { margin: 0.5rem 0; font-size: 1.35rem; color: var(--cima-verde-oscuro); }
      .certificado__codigo {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        margin: 1.5rem auto 1rem;
        padding: 0.75rem;
        background: var(--cima-verde-claro);
        border-radius: 8px;
      }
      .certificado__codigo-etiqueta { font-size: 0.95rem; color: var(--cima-texto-suave); }
      .certificado__codigo-valor { font-family: monospace; font-size: 1.15rem; font-weight: 700; word-break: break-word; }
      .certificado__nota { margin: 0; font-size: 0.95rem; color: var(--cima-texto-suave); }
      .acciones { display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1.5rem; }
      .enlace { display: inline-flex; align-items: center; justify-content: center; width: 100%; text-decoration: none; margin-top: 0.5rem; }
    `,
  ],
})
export class CertificadoPageComponent {
  private readonly servicio = inject(CertificationService);
  private readonly rutaId = inject(ActivatedRoute).snapshot.paramMap.get('rutaId') ?? '';

  readonly cargando = signal<boolean>(true);
  readonly error = signal<string | null>(null);
  readonly certificado = signal<Certificado | null>(null);

  readonly celular = computed(() => finalCelular(this.certificado()?.holder_phone_masked));
  readonly fecha = computed(() => fechaCertificado(this.certificado()?.issued_at ?? ''));
  readonly codigo = computed(() => codigoLegible(this.certificado()?.verification_code ?? ''));

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    if (!PATRON_UUID.test(this.rutaId)) {
      this.error.set(MENSAJE_NO_ENCONTRADO);
      this.cargando.set(false);
      return;
    }
    try {
      this.certificado.set(await this.servicio.obtener(this.rutaId));
    } catch (e: unknown) {
      if (!(e instanceof HttpErrorResponse)) {
        throw e;
      }
      this.error.set(mensajeError(e.status, e.error?.detail));
    } finally {
      this.cargando.set(false);
    }
  }

  /** Abre el diálogo del celular para imprimir o guardar el certificado como PDF. */
  imprimir(): void {
    window.print();
  }
}
