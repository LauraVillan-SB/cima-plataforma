import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';

import { mensajeDeError } from '../core/mensaje-error';
import { NotaGrabada, VozControlComponent } from '../voz/voz-control.component';
import {
  FaseChat,
  TIEMPO_MAXIMO_SEGUNDOS,
  esEstadoFinal,
  faseDeChat,
} from './chat';
import { ChatService, MensajeAceptado } from './chat.service';

/** Cada cuánto se consulta el estado de una inferencia pendiente. */
const INTERVALO_SONDEO_MS = 2000;

/** Mensaje de la conversación tal como se muestra en pantalla. */
interface Mensaje {
  readonly id: string;
  readonly canal: string;
  readonly entrada: string;
  readonly estado: string;
  readonly respuesta: string | null;
  /** Segundos pasados desde el envío, para el indicador de espera (Req 3.7). */
  readonly segundos: number;
  /** Segundos tras los cuales mostrar el indicador (`processing_after_seconds`). */
  readonly umbral: number;
  /** Texto original, solo en memoria y solo de esta sesión, para reintentar. */
  readonly textoParaReintento: string | null;
}

const TEXTO_NOTA_DE_VOZ = '🎤 Nota de voz';

/**
 * Pantalla del asistente conversacional (Tarea 23.2, Req 3, 14, 16). Envía
 * texto o notas de voz, consulta el estado hasta que hay respuesta y muestra el
 * historial. Pasados 15 s de espera muestra un indicador y a los 60 s informa
 * el error (Req 3.7, 3.8). La respuesta ya trae el prefijo que identifica a la
 * IA (Req 16.5), así que se muestra tal cual. Todo texto se pinta con
 * interpolación (nunca como HTML). La redacción de PII, los guardrails y el
 * control de acceso viven en el backend.
 */
@Component({
  selector: 'cima-chat-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [VozControlComponent],
  template: `
    <section class="chat">
      <h1 class="titulo">Tu asistente</h1>
      <p class="intro">
        Pregúntame sobre cultivo, tienda, clima o seguros. Te responde una inteligencia
        artificial; no pongas tu cédula ni datos de tu cuenta.
      </p>

      @if (cargandoHistorial()) {
        <p class="estado" role="status" aria-live="polite">Cargando tu conversación...</p>
      } @else if (errorHistorial(); as msg) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          {{ msg }}
          <button type="button" class="sb-ui-button sb-ui-button--secondary" (click)="cargarHistorial()">
            Reintentar
          </button>
        </div>
      }

      <div class="mensajes" role="log" aria-live="polite" aria-label="Conversación">
        @for (m of mensajes(); track m.id) {
          <article class="mensaje">
            <p class="burbuja burbuja--tu"><span class="quien">Tú:</span> {{ m.entrada }}</p>

            @switch (fase(m)) {
              @case ('esperando') {
                <p class="burbuja burbuja--estado" role="status">Enviado. Esperando la respuesta...</p>
              }
              @case ('procesando_lento') {
                <p class="burbuja burbuja--estado" role="status">
                  Estamos pensando tu respuesta. Gracias por esperar, ya casi.
                </p>
              }
              @case ('listo') {
                @if (m.respuesta) {
                  <p class="burbuja burbuja--ia">{{ m.respuesta }}</p>
                }
              }
              @case ('repetir_voz') {
                <div class="sb-ui-alert sb-ui-alert--info" role="status">
                  No alcanzamos a entender la nota de voz. Grábala otra vez, un poco más cerca y
                  despacio, o escribe tu mensaje.
                </div>
              }
              @case ('error') {
                <div class="sb-ui-alert sb-ui-alert--error" role="alert">
                  No pudimos darte una respuesta esta vez. Intenta de nuevo en un rato.
                  @if (m.textoParaReintento) {
                    <button
                      type="button"
                      class="sb-ui-button sb-ui-button--secondary"
                      (click)="reintentar(m)"
                    >
                      Intentar de nuevo
                    </button>
                  }
                </div>
              }
              @case ('tiempo_agotado') {
                <div class="sb-ui-alert sb-ui-alert--warning" role="alert">
                  Esto está tardando más de lo normal y no pudimos responderte. Puedes intentarlo
                  de nuevo.
                  @if (m.textoParaReintento) {
                    <button
                      type="button"
                      class="sb-ui-button sb-ui-button--secondary"
                      (click)="reintentar(m)"
                    >
                      Intentar de nuevo
                    </button>
                  }
                </div>
              }
            }
          </article>
        } @empty {
          @if (!cargandoHistorial() && !errorHistorial()) {
            <p class="estado">Aún no hay mensajes. Cuéntame qué quieres saber.</p>
          }
        }
      </div>

      @if (errorEnvio(); as msg) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">{{ msg }}</div>
      }

      <cima-voz-control
        [deshabilitado]="enviando()"
        (mensajeEnviado)="enviarTexto($event)"
        (notaGrabada)="enviarVoz($event)"
      />
    </section>
  `,
  styles: [
    `
      .chat {
        padding: 1.5rem 1rem;
        max-width: 640px;
        margin: 0 auto;
      }
      .titulo {
        margin: 0 0 0.5rem;
      }
      .intro,
      .estado {
        line-height: 1.5;
      }
      .mensajes {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin: 1rem 0;
      }
      .mensaje {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .burbuja {
        margin: 0;
        padding: 0.75rem 1rem;
        border-radius: 12px;
        line-height: 1.5;
        overflow-wrap: anywhere;
      }
      .burbuja--tu {
        background: #e7f6ec;
        align-self: flex-end;
        max-width: 90%;
      }
      .burbuja--ia {
        background: #f2f2f2;
        align-self: flex-start;
        max-width: 90%;
      }
      .burbuja--estado {
        background: #fff8e1;
        align-self: flex-start;
      }
      .quien {
        font-weight: 600;
      }
    `,
  ],
})
export class ChatPageComponent {
  private readonly chat = inject(ChatService);

  readonly mensajes = signal<readonly Mensaje[]>([]);
  readonly cargandoHistorial = signal<boolean>(true);
  readonly errorHistorial = signal<string | null>(null);
  readonly errorEnvio = signal<string | null>(null);
  readonly enviando = signal<boolean>(false);

  private readonly temporizadores = new Map<string, ReturnType<typeof setTimeout>>();
  private destruido = false;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.destruido = true;
      this.temporizadores.forEach((t) => clearTimeout(t));
      this.temporizadores.clear();
    });
    void this.cargarHistorial();
  }

  /** Fase visible del mensaje según su estado y el tiempo de espera. */
  fase(m: Mensaje): FaseChat {
    return faseDeChat(m.estado, m.segundos, m.umbral);
  }

  async cargarHistorial(): Promise<void> {
    this.cargandoHistorial.set(true);
    this.errorHistorial.set(null);
    try {
      const { items } = await this.chat.historial();
      const cargados = items.map<Mensaje>((i) => ({
        id: i.id,
        canal: i.input_channel,
        entrada: i.input_redacted || (i.input_channel === 'voz' ? TEXTO_NOTA_DE_VOZ : ''),
        estado: i.status,
        respuesta: i.response_text,
        segundos: 0,
        umbral: 15,
        textoParaReintento: null,
      }));
      this.mensajes.set(cargados);
      // Un mensaje pendiente de antes se sigue consultando hasta el límite.
      cargados.filter((m) => !esEstadoFinal(m.estado)).forEach((m) => this.vigilar(m.id));
    } catch (error) {
      this.errorHistorial.set(
        mensajeDeError(error, 'No pudimos cargar tu conversación. Revisa tu conexión.'),
      );
    } finally {
      this.cargandoHistorial.set(false);
    }
  }

  async enviarTexto(texto: string): Promise<void> {
    await this.enviar(
      () => this.chat.enviarTexto(texto),
      { canal: 'texto', entrada: texto, textoParaReintento: texto },
    );
  }

  async enviarVoz(nota: NotaGrabada): Promise<void> {
    await this.enviar(
      () => this.chat.enviarVoz(nota.audio, nota.mime, nota.duracionSegundos),
      { canal: 'voz', entrada: TEXTO_NOTA_DE_VOZ, textoParaReintento: null },
    );
  }

  async reintentar(m: Mensaje): Promise<void> {
    if (m.textoParaReintento) {
      await this.enviarTexto(m.textoParaReintento);
    }
  }

  private async enviar(
    peticion: () => Promise<MensajeAceptado>,
    base: Pick<Mensaje, 'canal' | 'entrada' | 'textoParaReintento'>,
  ): Promise<void> {
    this.enviando.set(true);
    this.errorEnvio.set(null);
    try {
      const acuse = await peticion();
      this.mensajes.update((actuales) => [
        ...actuales,
        {
          ...base,
          id: acuse.id,
          estado: acuse.status,
          respuesta: null,
          segundos: 0,
          umbral: acuse.processing_after_seconds,
        },
      ]);
      if (!esEstadoFinal(acuse.status)) {
        this.vigilar(acuse.id);
      }
    } catch (error) {
      this.errorEnvio.set(
        mensajeDeError(error, 'No pudimos enviar tu mensaje. Intenta de nuevo.'),
      );
    } finally {
      this.enviando.set(false);
    }
  }

  /**
   * Consulta el estado de un mensaje cada 2 s hasta que llega a un estado final
   * o se cumplen 60 s (Req 3.8). Un fallo puntual de red no corta la espera:
   * se reintenta en el siguiente ciclo y el límite de tiempo lo acota.
   */
  private vigilar(id: string): void {
    const inicio = Date.now();

    const paso = async (): Promise<void> => {
      if (this.destruido) {
        return;
      }
      const segundos = (Date.now() - inicio) / 1000;
      this.actualizar(id, { segundos });
      if (segundos >= TIEMPO_MAXIMO_SEGUNDOS) {
        return;
      }
      try {
        const resultado = await this.chat.consultar(id);
        this.actualizar(id, {
          estado: resultado.status,
          respuesta: resultado.response_text,
        });
        if (esEstadoFinal(resultado.status)) {
          return;
        }
      } catch {
        // Sin conexión por un momento: se vuelve a intentar en el próximo ciclo.
      }
      this.temporizadores.set(id, setTimeout(() => void paso(), INTERVALO_SONDEO_MS));
    };

    void paso();
  }

  private actualizar(id: string, cambios: Partial<Mensaje>): void {
    this.mensajes.update((actuales) =>
      actuales.map((m) => (m.id === id ? { ...m, ...cambios } : m)),
    );
  }
}
