import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { ChatPageComponent } from '../chat/chat-page.component';

/**
 * Boton flotante del asistente. Se muestra en cada microcapsula y abre un
 * panel con la conversacion sin sacar a la persona de la leccion: en celular
 * ocupa toda la pantalla y desde 640 px es una ventana en la esquina.
 *
 * El chat se carga bajo demanda la primera vez que se abre (no pesa en la
 * leccion) y reutiliza la pantalla del asistente tal cual: la redaccion de PII,
 * los guardrails y el control de acceso viven en el backend.
 *
 * Accesibilidad (Req 13.2, 13.3): boton de 56 px con `aria-expanded` y
 * `aria-controls`; el panel es un dialogo con nombre; al abrir el foco pasa al
 * boton "Cerrar" y al cerrar vuelve al boton flotante; Escape lo cierra.
 */
@Component({
  selector: 'cima-assistant-fab',
  imports: [ChatPageComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:keydown.escape)': 'alPresionarEscape()',
  },
  template: `
    <button
      #fab
      type="button"
      class="fab"
      aria-controls="panel-asistente"
      [attr.aria-expanded]="abierto()"
      (click)="alternar()"
    >
      <span aria-hidden="true">💬</span>
      <span>Asistente</span>
    </button>
    @if (abierto()) {
      <div id="panel-asistente" class="panel" role="dialog" aria-label="Asistente de CIMA">
        <div class="panel__cabecera">
          <button #cerrarBtn type="button" class="panel__cerrar" (click)="cerrar()">
            Cerrar
          </button>
        </div>
        <div class="panel__cuerpo">
          @defer (on immediate) {
            <cima-chat-page />
          } @placeholder {
            <p class="panel__estado" role="status">Abriendo tu asistente...</p>
          }
        </div>
      </div>
    }
  `,
  styles: [
    `
      :host {
        display: contents;
      }
      .fab {
        position: fixed;
        right: 1rem;
        bottom: calc(1rem + env(safe-area-inset-bottom, 0px));
        z-index: 25;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        width: max-content;
        max-width: calc(100vw - 2rem);
        white-space: nowrap;
        min-height: 56px;
        padding: 0 1.25rem;
        border: 3px solid var(--cima-verde-oscuro);
        border-radius: 999px;
        background: var(--cima-dorado);
        color: var(--cima-texto);
        font: inherit;
        font-size: 1.05rem;
        font-weight: 700;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
        cursor: pointer;
      }
      /* Celular: hoja a pantalla completa. */
      .panel {
        position: fixed;
        inset: 0;
        z-index: 40;
        display: flex;
        flex-direction: column;
        background: var(--cima-fondo);
      }
      .panel__cabecera {
        display: flex;
        justify-content: flex-end;
        padding: 0.5rem 0.75rem;
        background: var(--cima-verde-oscuro);
      }
      .panel__cerrar {
        padding: 0 1.25rem;
        border: 2px solid #fff;
        border-radius: 999px;
        background: transparent;
        color: #fff;
        font: inherit;
        font-size: 1.05rem;
        font-weight: 700;
        cursor: pointer;
      }
      .panel__cuerpo {
        flex: 1;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding-bottom: env(safe-area-inset-bottom, 0px);
      }
      .panel__estado {
        padding: 1rem;
      }
      /* Pantallas amplias: ventana en la esquina, encima del boton. */
      @media (min-width: 640px) {
        .panel {
          inset: auto 1rem 5.5rem auto;
          width: 26rem;
          height: min(40rem, calc(100svh - 7rem));
          overflow: hidden;
          border-radius: var(--cima-radio);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        }
      }
    `,
  ],
})
export class AssistantFabComponent {
  private readonly injector = inject(Injector);
  private readonly fab = viewChild.required<ElementRef<HTMLButtonElement>>('fab');
  private readonly botonCerrar = viewChild<ElementRef<HTMLButtonElement>>('cerrarBtn');

  protected readonly abierto = signal<boolean>(false);

  /** Abre o cierra el panel. */
  protected alternar(): void {
    if (this.abierto()) {
      this.cerrar();
    } else {
      this.abrir();
    }
  }

  /** Abre el panel y lleva el foco a "Cerrar" cuando ya se pintó. */
  private abrir(): void {
    this.abierto.set(true);
    afterNextRender(() => this.botonCerrar()?.nativeElement.focus(), {
      injector: this.injector,
    });
  }

  /** Cierra el panel y devuelve el foco al boton flotante. */
  protected cerrar(): void {
    this.abierto.set(false);
    this.fab().nativeElement.focus();
  }

  /** Escape cierra el panel si esta abierto. */
  protected alPresionarEscape(): void {
    if (this.abierto()) {
      this.cerrar();
    }
  }
}
