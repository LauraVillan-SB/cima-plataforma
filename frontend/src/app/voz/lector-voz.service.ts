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

  /** Posición del texto que se está diciendo en una lectura por partes, o null. */
  readonly segmento = signal<number | null>(null);

  /** Cambia en cada lectura nueva: los avisos de una lectura cancelada se ignoran. */
  private turno = 0;

  /** Lee la respuesta del mensaje `id`; si ya se estaba leyendo otra, la corta. */
  leer(id: string, respuesta: string): void {
    this.leerPorPartes(id, [respuesta]);
  }

  /**
   * Lee varios textos seguidos (por ejemplo, los párrafos de la página) y avisa en
   * `segmento` cuál se está diciendo, para resaltarlo en pantalla. Leer por partes
   * además evita que algunos navegadores corten las lecturas largas.
   */
  leerPorPartes(id: string, textos: readonly string[]): void {
    const sintesis = this.sintesis;
    const limpios = textos.map(textoParaLeer);
    const ultimo = limpios.reduce((u, texto, i) => (texto ? i : u), -1);
    if (!sintesis || ultimo < 0) {
      return;
    }
    sintesis.cancel();
    const turno = ++this.turno;
    const terminar = () => {
      if (this.turno === turno) {
        this.leyendo.set(null);
        this.segmento.set(null);
      }
    };
    limpios.forEach((texto, indice) => {
      if (!texto) {
        return;
      }
      const enunciado = this.enunciado(texto);
      enunciado.onstart = () => {
        if (this.turno === turno) {
          this.segmento.set(indice);
        }
      };
      enunciado.onerror = terminar;
      if (indice === ultimo) {
        enunciado.onend = terminar;
      }
      sintesis.speak(enunciado);
    });
    this.leyendo.set(id);
  }

  /** Detiene la lectura en curso. */
  detener(): void {
    this.turno++;
    this.sintesis?.cancel();
    this.leyendo.set(null);
    this.segmento.set(null);
  }

  private enunciado(texto: string): SpeechSynthesisUtterance {
    const enunciado = new SpeechSynthesisUtterance(texto);
    enunciado.lang = this.voz?.lang ?? 'es-CO';
    if (this.voz) {
      enunciado.voice = this.voz;
    }
    enunciado.rate = 0.95;
    return enunciado;
  }

  private cargarVoz(): void {
    this.voz = this.sintesis ? elegirVoz(this.sintesis.getVoices()) : null;
  }
}
