import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { ChatPageComponent } from '../chat/chat-page.component';

/**
 * Recuerda, mientras dure la sesion de la app, si la persona ya cerro el
 * saludo: asi no reaparece al cambiar de pantalla. Solo guarda un booleano en
 * memoria (no hay datos personales ni almacenamiento del navegador).
 */
let saludoYaCerrado = false;

/**
 * Asistente flotante CIMA. Se muestra en todas las pantallas con sesion como un
 * boton circular amarillo con contorno blanco, icono y nombre en verde, y un
 * globo de saludo con una "x" para cerrarlo. Al tocar el boton se abre el chat
 * en un panel, sin sacar a la persona de la pantalla en la que esta: en celular
 * ocupa toda la pantalla y desde 640 px es una ventana en la esquina.
 *
 * El chat se carga bajo demanda la primera vez que se abre y reutiliza la
 * pantalla del asistente tal cual: la redaccion de PII, los guardrails y el
 * control de acceso viven en el backend.
 *
 * Accesibilidad (Req 13.2, 13.3): el boton mide 88 px, su nombre accesible
 * contiene el texto visible ("CIMA"), tiene `aria-expanded` y `aria-controls`;
 * el texto y el icono van en verde oscuro sobre amarillo (contraste mayor a
 * 6:1); el saludo se cierra con un boton de 44 px; el panel es un dialogo con
 * nombre; al abrir el foco pasa a "Cerrar" y al cerrar vuelve al boton; Escape
 * lo cierra.
 */
@Component({
  selector: 'cima-assistant-fab',
  imports: [ChatPageComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:keydown.escape)': 'alPresionarEscape()',
  },
  template: `
    <div class="widget">
      @if (saludoVisible()) {
        <div class="saludo">
          <span class="saludo__barra" aria-hidden="true"></span>
          <p class="saludo__texto">
            <strong>Cuéntame, ¿qué necesitas?</strong>
            Soy tu asistente virtual CIMA
          </p>
          <button
            type="button"
            class="saludo__cerrar"
            aria-label="Cerrar el saludo del asistente CIMA"
            (click)="cerrarSaludo()"
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
      }
      <button
        #fab
        type="button"
        class="fab"
        aria-label="Abrir el asistente CIMA"
        aria-controls="panel-asistente"
        [attr.aria-expanded]="abierto()"
        (click)="alternar()"
      >
        <svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true" focusable="false">
          <path
            d="M4 4h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-6l-4 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linejoin="round"
          />
          <circle cx="9" cy="10" r="1.1" fill="currentColor" />
          <circle cx="15" cy="10" r="1.1" fill="currentColor" />
          <path
            d="M9 13.2c.8.8 1.8 1.2 3 1.2s2.2-.4 3-1.2"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg>
        <span class="fab__texto" aria-hidden="true">CIMA</span>
      </button>
    </div>
    @if (abierto()) {
      <div id="panel-asistente" class="panel" role="dialog" aria-label="Asistente CIMA">
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
      /* Conjunto fijo abajo a la derecha: globo de saludo + boton circular. */
      .widget {
        position: fixed;
        right: 1rem;
        bottom: calc(1rem + env(safe-area-inset-bottom, 0px));
        z-index: 25;
        display: flex;
        align-items: flex-end;
        gap: 0.5rem;
        width: max-content;
        max-width: calc(100vw - 2rem);
      }
      /* Amarillo con contorno blanco; icono y texto en verde oscuro. */
      .fab {
        flex: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.15rem;
        width: 88px;
        height: 88px;
        padding: 0;
        border: 3px solid #fff;
        border-radius: 50%;
        background: var(--cima-dorado);
        color: var(--cima-verde-oscuro);
        font: inherit;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        cursor: pointer;
      }
      .fab__texto {
        font-size: 0.85rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        line-height: 1;
      }
      .saludo {
        position: relative;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-width: 0;
        max-width: min(18rem, calc(100vw - 88px - 3.5rem));
        padding: 0.6rem 0.4rem 0.6rem 0;
        margin-bottom: 0.5rem;
        border-radius: 10px;
        background: var(--cima-dorado);
        color: var(--cima-texto);
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
      }
      .saludo__barra {
        align-self: stretch;
        flex: none;
        width: 5px;
        margin-left: 0.6rem;
        border-radius: 3px;
        background: var(--cima-verde-oscuro);
      }
      .saludo__texto {
        flex: 1;
        min-width: 0;
        margin: 0;
        font-size: 0.85rem;
        line-height: 1.35;
      }
      .saludo__texto strong {
        display: block;
        font-size: 0.95rem;
      }
      .saludo__cerrar {
        flex: none;
        align-self: flex-start;
        display: grid;
        place-items: center;
        width: 44px;
        height: 44px;
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: var(--cima-texto);
        font: inherit;
        font-size: 1.1rem;
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
          inset: auto 1rem 7.5rem auto;
          width: 26rem;
          height: min(40rem, calc(100svh - 9rem));
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
  private readonly saludoCerrado = signal<boolean>(saludoYaCerrado);

  /** El saludo se ve hasta que la persona lo cierre o abra el asistente. */
  protected readonly saludoVisible = computed(
    () => !this.saludoCerrado() && !this.abierto(),
  );

  /** Cierra el globo de saludo y lo recuerda mientras dure la sesion de la app. */
  protected cerrarSaludo(): void {
    saludoYaCerrado = true;
    this.saludoCerrado.set(true);
  }

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
