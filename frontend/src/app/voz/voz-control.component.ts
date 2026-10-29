import { ChangeDetectionStrategy, Component, output, signal } from '@angular/core';

/**
 * Control voz-first con alternativa de texto en el mismo flujo (Tarea 23.2).
 *
 * El modo primario es por voz: un boton grande (≥ 44×44 px, operable con una
 * mano) para grabar/enviar una nota de voz, y una entrada de texto alternativa
 * siempre visible para quien prefiera escribir (Req 14.1, 14.2, 14.4). La
 * captura real de audio se integra con la API del navegador; aqui se expone el
 * contrato de salida. Solo presentacion.
 */
@Component({
  selector: 'cima-voz-control',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="voz">
      <button
        type="button"
        class="boton-voz"
        [attr.aria-pressed]="grabando()"
        [attr.aria-label]="grabando() ? 'Detener grabacion' : 'Hablar'"
        (click)="alternarGrabacion()"
      >
        {{ grabando() ? '● Grabando... toca para enviar' : '🎤 Hablar' }}
      </button>

      <label for="texto-alt" class="texto-alt-label">O escribe tu mensaje</label>
      <textarea
        id="texto-alt"
        class="texto-alt"
        rows="2"
        [value]="texto()"
        (input)="texto.set($any($event.target).value)"
        placeholder="Escribe aqui si prefieres"
      ></textarea>
      <button type="button" class="boton-enviar" (click)="enviarTexto()">Enviar</button>
    </div>
  `,
  styles: [
    `
      .voz {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 12px;
      }
      .boton-voz {
        min-height: 56px;
        min-width: 56px;
        font-size: 1.1rem;
        color: #fff;
        background: #0a7d3c;
        border: none;
        border-radius: 12px;
      }
      .boton-voz[aria-pressed='true'] {
        background: #8a1f1f;
      }
      .texto-alt-label {
        font-weight: 600;
      }
      .texto-alt {
        width: 100%;
        min-height: 44px;
        font-size: 1rem;
        padding: 8px;
        border: 2px solid #0a7d3c;
        border-radius: 8px;
      }
      .boton-enviar {
        min-height: 44px;
        font-size: 1rem;
        color: #0a5a2c;
        background: #e7f6ec;
        border: 2px solid #0a7d3c;
        border-radius: 8px;
      }
    `,
  ],
})
export class VozControlComponent {
  /** Emite el texto (desde voz transcrita o escrito) para que lo procese el padre. */
  readonly mensajeEnviado = output<string>();

  readonly grabando = signal<boolean>(false);
  readonly texto = signal<string>('');

  alternarGrabacion(): void {
    // Integracion real con MediaRecorder/STT se conecta al pipeline de voz del
    // backend; aqui solo se alterna el estado visible.
    this.grabando.update((v) => !v);
  }

  enviarTexto(): void {
    const valor = this.texto().trim();
    if (valor) {
      this.mensajeEnviado.emit(valor);
      this.texto.set('');
    }
  }
}
