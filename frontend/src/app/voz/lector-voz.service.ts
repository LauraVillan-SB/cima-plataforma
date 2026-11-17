import { Injectable, signal } from '@angular/core';

import { elegirVoz, textoParaLeer } from './voz';

/**
 * Lee en voz alta las respuestas del asistente con la voz del propio celular
 * (Web Speech API, Req 14.3). No descarga audio: no gasta datos y funciona sin
 * conexión. La voz depende del dispositivo; se prefiere español de Colombia.
 *
 * Solo lee texto que ya pasó por los filtros del backend. Si el navegador no
 * tiene síntesis de voz, `disponible` es falso y la pantalla no ofrece leer.
 */
@Injectable({ providedIn: 'root' })
export class LectorVozService {
  /** Id del mensaje que se está leyendo, o null. */
  readonly leyendo = signal<string | null>(null);

  private readonly sintesis: SpeechSynthesis | null =
    typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;

  private voz: SpeechSynthesisVoice | null = null;

  constructor() {
    if (this.sintesis) {
      this.cargarVoz();
      // En varios navegadores la lista de voces llega después de cargar la página.
      this.sintesis.addEventListener?.('voiceschanged', () => this.cargarVoz());
    }
  }

  /** Verdadero si el navegador puede leer en voz alta. */
  get disponible(): boolean {
    return this.sintesis !== null;
  }

  /** Lee la respuesta del mensaje `id`; si ya se estaba leyendo otra, la corta. */
  leer(id: string, respuesta: string): void {
    const sintesis = this.sintesis;
    const texto = textoParaLeer(respuesta);
    if (!sintesis || !texto) {
      return;
    }
    sintesis.cancel();
    const enunciado = new SpeechSynthesisUtterance(texto);
    enunciado.lang = this.voz?.lang ?? 'es-CO';
    if (this.voz) {
      enunciado.voice = this.voz;
    }
    enunciado.rate = 0.95;
    const terminar = () => {
      if (this.leyendo() === id) {
        this.leyendo.set(null);
      }
    };
    enunciado.onend = terminar;
    enunciado.onerror = terminar;
    this.leyendo.set(id);
    sintesis.speak(enunciado);
  }

  /** Detiene la lectura en curso. */
  detener(): void {
    this.sintesis?.cancel();
    this.leyendo.set(null);
  }

  private cargarVoz(): void {
    this.voz = this.sintesis ? elegirVoz(this.sintesis.getVoices()) : null;
  }
}
