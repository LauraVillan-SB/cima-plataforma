/**
 * Lógica pura de voz (sin Angular ni APIs del navegador) para probarla con jest.
 *
 * 1. Detección de silencio antes de enviar una nota de voz: Gemini puede
 *    inventar frases cuando recibe silencio, así que el cliente no envía una
 *    nota en la que casi no se escuchó voz. Es una ayuda de presentación: el
 *    servidor igual pide repetir si el modelo no entendió (Req 14.5).
 * 2. Lectura en voz alta de las respuestas con la voz del celular (Web Speech
 *    API, Req 14.3): qué voz elegir y qué texto leer.
 */

/** Cada cuánto se mide el nivel del micrófono durante la grabación. */
export const INTERVALO_MEDICION_MS = 100;

/**
 * Nivel RMS (0 a 1) a partir del cual una medición cuenta como voz. Una voz
 * normal a un palmo del celular suele dar 0,05–0,3; el silencio o el ruido de
 * fondo de una habitación, menos de 0,01.
 */
export const UMBRAL_NIVEL_VOZ = 0.02;

/** Segundos mínimos con voz para enviar la nota (una palabra corta dura ~0,3 s). */
export const SEGUNDOS_MINIMOS_CON_VOZ = 0.4;

/** Nivel RMS de un bloque de muestras de audio en [-1, 1]. Vacío o inválido → 0. */
export function nivelRms(muestras: ArrayLike<number>): number {
  if (muestras.length === 0) {
    return 0;
  }
  let suma = 0;
  for (let i = 0; i < muestras.length; i++) {
    const valor = muestras[i];
    if (!Number.isFinite(valor)) {
      return 0;
    }
    suma += valor * valor;
  }
  return Math.sqrt(suma / muestras.length);
}

/**
 * Indica si en las mediciones hubo voz suficiente para enviar la nota.
 *
 * @param niveles niveles RMS medidos cada `intervaloMs` durante la grabación.
 */
export function hayVozSuficiente(
  niveles: readonly number[],
  intervaloMs: number = INTERVALO_MEDICION_MS,
  umbral: number = UMBRAL_NIVEL_VOZ,
  minimoSegundos: number = SEGUNDOS_MINIMOS_CON_VOZ,
): boolean {
  const conVoz = niveles.filter((nivel) => Number.isFinite(nivel) && nivel >= umbral).length;
  return (conVoz * intervaloMs) / 1000 >= minimoSegundos;
}

/**
 * Indica si la medición sirve para decidir. Solo se confía en ella si el
 * `AudioContext` quedó corriendo (un contexto suspendido entrega ceros aunque
 * haya voz) y hubo mediciones. Con un contexto corriendo, todo en cero sí es
 * silencio (por ejemplo, micrófono silenciado) y la nota no se envía.
 */
export function medicionConfiable(contextoCorriendo: boolean, niveles: readonly number[]): boolean {
  return contextoCorriendo && niveles.length > 0;
}

/** Lo mínimo que se necesita de una voz del navegador (`SpeechSynthesisVoice`). */
export interface VozDisponible {
  readonly lang: string;
}

/** Variantes de español en orden de preferencia: primero Colombia, luego Latinoamérica. */
const PREFERENCIA_IDIOMA: readonly string[] = ['es-co', 'es-419', 'es-us', 'es-mx'];

function normalizarIdioma(lang: string): string {
  return lang.replace(/_/g, '-').toLowerCase();
}

/**
 * Elige la voz del celular para leer las respuestas: español de Colombia si
 * existe, luego otras variantes latinoamericanas y por último cualquier
 * español. Si no hay ninguna en español devuelve null y no se ofrece leer.
 */
export function elegirVoz<T extends VozDisponible>(voces: readonly T[]): T | null {
  for (const preferido of PREFERENCIA_IDIOMA) {
    const voz = voces.find((v) => normalizarIdioma(v.lang) === preferido);
    if (voz) {
      return voz;
    }
  }
  return voces.find((v) => normalizarIdioma(v.lang).startsWith('es')) ?? null;
}

/**
 * Prepara la respuesta para leerla en voz alta: quita emojis y signos de
 * formato que la voz pronunciaría ("asterisco") y une los espacios. El texto
 * ya pasó por los filtros del backend; aquí solo se limpia la forma.
 */
export function textoParaLeer(respuesta: string): string {
  return respuesta
    .replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, ' ')
    .replace(/[*_#`~>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
