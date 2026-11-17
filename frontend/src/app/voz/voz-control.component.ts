import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

import {
  TEXTO_MAX,
  VOZ_MAX_SEGUNDOS,
  duracionVozValida,
  elegirMimeAudio,
  textoValido,
} from '../chat/chat';
import { INTERVALO_MEDICION_MS, hayVozSuficiente, medicionConfiable, nivelRms } from './voz';

/** `AudioContext` con el prefijo que aún usan algunos navegadores de iOS. */
type ConstructorContexto = new () => AudioContext;

/** Nota de voz grabada, lista para enviarse al servidor (Req 14.2). */
export interface NotaGrabada {
  readonly audio: Blob;
  readonly mime: string;
  readonly duracionSegundos: number;
}

/** Se corta la grabación un poco antes del máximo para no pasarse de 120 s. */
const CORTE_GRABACION_MS = (VOZ_MAX_SEGUNDOS - 2) * 1000;

/**
 * Control voz-first con alternativa de texto en el mismo flujo (Tarea 23.2).
 *
 * El modo primario es por voz: un botón grande (≥ 44×44 px, operable con una
 * mano) que graba con `MediaRecorder` y emite la nota al tocarlo de nuevo, y
 * una entrada de texto siempre visible para quien prefiera escribir (Req 14.1,
 * 14.2, 14.4). Solo se ofrece grabar si el navegador produce un formato que el
 * servidor acepta; si no, queda el texto. Los límites de aquí son solo ayuda de
 * presentación: el servidor valida duración, tamaño y formato.
 */
@Component({
  selector: 'cima-voz-control',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="voz">
      @if (mimeAudio) {
        <button
          type="button"
          class="boton-voz"
          [attr.aria-pressed]="grabando()"
          [disabled]="deshabilitado()"
          (click)="alternarGrabacion()"
        >
          {{ grabando() ? '● Grabando... toca para enviar' : '🎤 Hablar' }}
        </button>
      } @else {
        <p class="aviso" role="status">
          Aquí no podemos grabar notas de voz. Escribe tu mensaje y te respondemos igual.
        </p>
      }

      @if (aviso()) {
        <p class="aviso" role="status">{{ aviso() }}</p>
      }

      <label for="texto-alt" class="texto-alt-label">O escribe tu mensaje</label>
      <textarea
        id="texto-alt"
        class="texto-alt"
        rows="3"
        [maxLength]="textoMax"
        [value]="texto()"
        (input)="texto.set($any($event.target).value)"
        placeholder="Escribe aquí si prefieres"
      ></textarea>
      <button
        type="button"
        class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large"
        [disabled]="deshabilitado() || !puedeEnviarTexto()"
        (click)="enviarTexto()"
      >
        Enviar
      </button>
    </div>
  `,
  styles: [
    `
      .voz {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 12px 0;
      }
      .boton-voz {
        min-height: 64px;
        min-width: 64px;
        font-size: 1.1rem;
        color: #fff;
        background: #0a7d3c;
        border: none;
        border-radius: 12px;
      }
      .boton-voz[aria-pressed='true'] {
        background: #8a1f1f;
      }
      .boton-voz:disabled {
        opacity: 0.6;
      }
      .aviso {
        margin: 0;
        line-height: 1.5;
      }
      .texto-alt-label {
        font-weight: 600;
      }
      .texto-alt {
        width: 100%;
        box-sizing: border-box;
        min-height: 44px;
        font-size: 1rem;
        padding: 8px;
        border: 2px solid #0a7d3c;
        border-radius: 8px;
      }
    `,
  ],
})
export class VozControlComponent {
  /** Deshabilita el control mientras el padre envía un mensaje. */
  readonly deshabilitado = input<boolean>(false);

  /** Emite el texto escrito para que lo procese el padre. */
  readonly mensajeEnviado = output<string>();

  /** Emite la nota de voz grabada para que la procese el padre. */
  readonly notaGrabada = output<NotaGrabada>();

  readonly grabando = signal<boolean>(false);
  readonly texto = signal<string>('');
  readonly aviso = signal<string | null>(null);
  readonly textoMax = TEXTO_MAX;

  /** Formato de grabación disponible, o null si el navegador no sirve para voz. */
  readonly mimeAudio: string | null = this.detectarMime();

  private grabadora: MediaRecorder | null = null;
  private flujo: MediaStream | null = null;
  private fragmentos: Blob[] = [];
  private inicioMs = 0;
  private temporizador: ReturnType<typeof setTimeout> | null = null;

  /** Medición del nivel del micrófono para no enviar notas en silencio. */
  private contextoAudio: AudioContext | null = null;
  private medidor: ReturnType<typeof setInterval> | null = null;
  private niveles: number[] = [];
  /** Si el contexto quedó corriendo; solo así los ceros significan silencio. */
  private contextoCorriendo = false;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.liberar());
  }

  puedeEnviarTexto(): boolean {
    return textoValido(this.texto());
  }

  async alternarGrabacion(): Promise<void> {
    if (this.grabando()) {
      this.grabadora?.stop();
      return;
    }
    await this.iniciarGrabacion();
  }

  enviarTexto(): void {
    if (!this.puedeEnviarTexto()) {
      return;
    }
    this.mensajeEnviado.emit(this.texto().trim());
    this.texto.set('');
  }

  private async iniciarGrabacion(): Promise<void> {
    const mime = this.mimeAudio;
    if (!mime) {
      return;
    }
    this.aviso.set(null);
    try {
      this.flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      this.aviso.set('No pudimos usar el micrófono. Revisa el permiso o escribe tu mensaje.');
      return;
    }
    this.fragmentos = [];
    const grabadora = new MediaRecorder(this.flujo, { mimeType: mime });
    grabadora.ondataavailable = (evento) => {
      if (evento.data.size > 0) {
        this.fragmentos.push(evento.data);
      }
    };
    grabadora.onstop = () => this.terminarGrabacion(mime);
    this.grabadora = grabadora;
    this.inicioMs = Date.now();
    await this.iniciarMedicion(this.flujo);
    grabadora.start();
    this.grabando.set(true);
    this.temporizador = setTimeout(() => grabadora.stop(), CORTE_GRABACION_MS);
  }

  private terminarGrabacion(mime: string): void {
    const duracionSegundos = (Date.now() - this.inicioMs) / 1000;
    const audio = new Blob(this.fragmentos, { type: mime });
    const niveles = this.niveles;
    // Si no se pudo medir (sin Web Audio o contexto suspendido) no se bloquea:
    // el servidor igual pide repetir si no se entendió.
    const medicionValida = medicionConfiable(this.contextoCorriendo, niveles);
    this.liberar();
    if (!duracionVozValida(duracionSegundos)) {
      this.aviso.set('La nota quedó muy corta. Habla un poco más y vuelve a intentar.');
      return;
    }
    if (medicionValida && !hayVozSuficiente(niveles)) {
      this.aviso.set(
        'No alcanzamos a escuchar tu voz. Habla más cerca del celular y vuelve a intentar.',
      );
      return;
    }
    this.notaGrabada.emit({ audio, mime, duracionSegundos });
  }

  /**
   * Mide el nivel del micrófono cada 100 ms mientras se graba. El audio no sale
   * de aquí: solo se guarda un número por medición, en memoria.
   */
  private async iniciarMedicion(flujo: MediaStream): Promise<void> {
    this.niveles = [];
    const ventana = window as unknown as {
      AudioContext?: ConstructorContexto;
      webkitAudioContext?: ConstructorContexto;
    };
    const Contexto = ventana.AudioContext ?? ventana.webkitAudioContext;
    if (!Contexto) {
      return;
    }
    try {
      const contexto = new Contexto();
      if (contexto.state === 'suspended') {
        await contexto.resume();
      }
      const analizador = contexto.createAnalyser();
      analizador.fftSize = 2048;
      contexto.createMediaStreamSource(flujo).connect(analizador);
      const muestras = new Float32Array(analizador.fftSize);
      this.contextoAudio = contexto;
      this.contextoCorriendo = contexto.state === 'running';
      this.medidor = setInterval(() => {
        analizador.getFloatTimeDomainData(muestras);
        this.niveles.push(nivelRms(muestras));
      }, INTERVALO_MEDICION_MS);
    } catch (error) {
      // Sin medición se graba igual; solo se pierde esta ayuda.
      if (!(error instanceof DOMException) && !(error instanceof TypeError)) {
        throw error;
      }
    }
  }

  /** Apaga el micrófono, el temporizador y el estado de grabación. */
  private liberar(): void {
    if (this.temporizador) {
      clearTimeout(this.temporizador);
      this.temporizador = null;
    }
    if (this.medidor) {
      clearInterval(this.medidor);
      this.medidor = null;
    }
    void this.contextoAudio?.close();
    this.contextoAudio = null;
    this.contextoCorriendo = false;
    this.niveles = [];
    this.flujo?.getTracks().forEach((pista) => pista.stop());
    this.flujo = null;
    this.grabadora = null;
    this.grabando.set(false);
  }

  private detectarMime(): string | null {
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      return null;
    }
    return elegirMimeAudio((mime) => MediaRecorder.isTypeSupported(mime));
  }
}
