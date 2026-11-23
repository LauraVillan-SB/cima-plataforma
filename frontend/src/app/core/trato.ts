/**
 * Cómo quiere la persona que la app le diga ("doña Rosa", "don Carlos" o solo
 * "Rosa"). Lógica pura (sin Angular) para poder probarla con jest. Req 13.1.
 *
 * El nombre es un dato personal y el Perfil del backend no lo guarda (Req 9:
 * solo teléfono, actividad y zona). Por eso la preferencia vive SOLO en este
 * celular (`localStorage`): nunca viaja al servidor, a los registros ni al
 * asistente (Req 3.10). Es opcional; sin ella la app habla de "usted".
 *
 * Al cambiar la sesión de manos (salir, entrar, registrarse o expirar) se borra
 * junto con los demás datos locales, porque en un celular compartido el
 * siguiente que entre no debe ver el nombre de otra persona.
 */

/** Clave en `localStorage`. La versión permite cambiar el formato sin leer datos viejos. */
export const CLAVE_TRATO = 'cima-trato-v1';

/** Largo máximo del nombre: alcanza para "María de los Ángeles". */
export const MAX_NOMBRE = 30;

/** Opciones de trato: "don", "doña" o solo el nombre. */
export type Trato = 'don' | 'dona' | 'nombre';

export const TRATOS: readonly { readonly valor: Trato; readonly etiqueta: string }[] = [
  { valor: 'dona', etiqueta: 'Doña' },
  { valor: 'don', etiqueta: 'Don' },
  { valor: 'nombre', etiqueta: 'Solo mi nombre' },
];

/** Preferencia guardada en el celular. */
export interface PreferenciaTrato {
  readonly trato: Trato;
  readonly nombre: string;
}

/**
 * Solo letras (con tildes y ñ), espacios, apóstrofo y guion, empezando por letra.
 * Sin dígitos ni signos: así no se cuela un celular, una cédula, un correo ni
 * nada que parezca marcado.
 */
const NOMBRE_VALIDO = /^\p{L}[\p{L}' -]*$/u;

/** Indica si el valor es una de las opciones de trato. */
export function esTrato(valor: unknown): valor is Trato {
  return valor === 'don' || valor === 'dona' || valor === 'nombre';
}

/**
 * Normaliza el nombre escrito: quita espacios de sobra y pone en mayúscula la
 * primera letra de cada palabra ("rosa maría" → "Rosa María").
 *
 * @returns el nombre listo para mostrar, o `null` si está vacío, es muy largo o
 *   trae caracteres no permitidos.
 */
export function normalizarNombre(texto: unknown): string | null {
  if (typeof texto !== 'string') {
    return null;
  }
  const limpio = texto.normalize('NFC').split(/\s+/).filter(Boolean).join(' ');
  if (!limpio || limpio.length > MAX_NOMBRE || !NOMBRE_VALIDO.test(limpio)) {
    return null;
  }
  return limpio
    .split(' ')
    .map((palabra) => palabra.charAt(0).toLocaleUpperCase('es-CO') + palabra.slice(1))
    .join(' ');
}

/** Arma la preferencia validada, o `null` si el trato o el nombre no son válidos. */
export function crearPreferencia(trato: unknown, nombre: unknown): PreferenciaTrato | null {
  const limpio = normalizarNombre(nombre);
  return esTrato(trato) && limpio ? { trato, nombre: limpio } : null;
}

/** Cómo llamar a la persona: "doña Rosa", "don Carlos", "Rosa" o vacío si no hay preferencia. */
export function comoLlamar(preferencia: PreferenciaTrato | null): string {
  if (!preferencia) {
    return '';
  }
  const prefijos: Record<Trato, string> = { don: 'don ', dona: 'doña ', nombre: '' };
  return `${prefijos[preferencia.trato]}${preferencia.nombre}`;
}

/** Lo mínimo de `Storage` que se usa. */
export interface AlmacenClaveValor {
  getItem(clave: string): string | null;
  setItem(clave: string, valor: string): void;
  removeItem(clave: string): void;
}

/** `localStorage` del navegador, o indefinido si no existe o está bloqueado. */
export function almacenLocal(): AlmacenClaveValor | undefined {
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage;
  } catch (error: unknown) {
    // Algunos navegadores bloquean el acceso (modo privado o permisos): sin
    // almacén, la app sigue hablando de "usted".
    if (error instanceof DOMException) {
      return undefined;
    }
    throw error;
  }
}

/**
 * Lee la preferencia guardada. Zero Trust: el valor se vuelve a validar, porque
 * cualquiera con el celular puede editar el `localStorage`.
 */
export function leerTrato(almacen: AlmacenClaveValor | undefined): PreferenciaTrato | null {
  const crudo = almacen?.getItem(CLAVE_TRATO);
  if (!crudo) {
    return null;
  }
  let dato: unknown;
  try {
    dato = JSON.parse(crudo);
  } catch (error: unknown) {
    if (error instanceof SyntaxError) {
      return null;
    }
    throw error;
  }
  if (typeof dato !== 'object' || dato === null) {
    return null;
  }
  const { trato, nombre } = dato as Record<string, unknown>;
  return crearPreferencia(trato, nombre);
}

/**
 * Guarda la preferencia en el celular.
 *
 * @returns `true` si quedó guardada; `false` si no hay almacén o el navegador lo
 *   rechazó (sin espacio o bloqueado).
 */
export function guardarTrato(
  almacen: AlmacenClaveValor | undefined,
  preferencia: PreferenciaTrato,
): boolean {
  if (!almacen) {
    return false;
  }
  try {
    almacen.setItem(
      CLAVE_TRATO,
      JSON.stringify({ trato: preferencia.trato, nombre: preferencia.nombre }),
    );
    return true;
  } catch (error: unknown) {
    if (error instanceof DOMException) {
      return false;
    }
    throw error;
  }
}

/** Borra la preferencia del celular. */
export function borrarTrato(almacen: AlmacenClaveValor | undefined): void {
  almacen?.removeItem(CLAVE_TRATO);
}
