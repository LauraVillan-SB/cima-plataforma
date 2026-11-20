import {
  AlmacenClaveValor,
  CLAVE_TRATO,
  MAX_NOMBRE,
  borrarTrato,
  comoLlamar,
  crearPreferencia,
  guardarTrato,
  leerTrato,
  normalizarNombre,
} from './trato';

/**
 * Pruebas de "¿Cómo quiere que le digamos?" (Req 13.1). El nombre solo vive en
 * el celular y se valida al escribirlo y al leerlo (Zero Trust).
 */

class AlmacenFalso implements AlmacenClaveValor {
  readonly datos = new Map<string, string>();
  constructor(private readonly fallaAlGuardar = false) {}
  getItem(clave: string): string | null {
    return this.datos.get(clave) ?? null;
  }
  setItem(clave: string, valor: string): void {
    if (this.fallaAlGuardar) {
      throw new DOMException('lleno', 'QuotaExceededError');
    }
    this.datos.set(clave, valor);
  }
  removeItem(clave: string): void {
    this.datos.delete(clave);
  }
}

describe('normalizarNombre', () => {
  it('quita espacios de sobra y pone mayúscula inicial en cada palabra', () => {
    expect(normalizarNombre('  rosa   maría ')).toBe('Rosa María');
    expect(normalizarNombre('ÁNGELA')).toBe('ÁNGELA');
    expect(normalizarNombre('josé-luis')).toBe('José-luis');
  });

  it.each([
    ['vacío', ''],
    ['solo espacios', '   '],
    ['un celular', '3001234567'],
    ['letras y números', 'Rosa 4567'],
    ['un correo', 'rosa@correo.com'],
    ['marcado', '<b>Rosa</b>'],
    ['empieza con guion', '-Rosa'],
    ['no es texto', 42],
  ])('rechaza %s', (_caso, valor) => {
    expect(normalizarNombre(valor)).toBeNull();
  });

  it('rechaza un nombre más largo que el máximo', () => {
    expect(normalizarNombre('a'.repeat(MAX_NOMBRE))).not.toBeNull();
    expect(normalizarNombre('a'.repeat(MAX_NOMBRE + 1))).toBeNull();
  });
});

describe('comoLlamar', () => {
  it('antepone don o doña según lo escogido', () => {
    expect(comoLlamar(crearPreferencia('dona', 'rosa'))).toBe('doña Rosa');
    expect(comoLlamar(crearPreferencia('don', 'carlos'))).toBe('don Carlos');
    expect(comoLlamar(crearPreferencia('nombre', 'rosa'))).toBe('Rosa');
  });

  it('sin preferencia queda vacío y la app sigue hablando de "usted"', () => {
    expect(comoLlamar(null)).toBe('');
    expect(crearPreferencia('señora', 'Rosa')).toBeNull();
    expect(crearPreferencia('dona', '')).toBeNull();
  });
});

describe('guardar, leer y borrar en el celular', () => {
  it('guarda y vuelve a leer la misma preferencia', () => {
    const almacen = new AlmacenFalso();
    const preferencia = crearPreferencia('dona', 'Rosa')!;
    expect(guardarTrato(almacen, preferencia)).toBe(true);
    expect(leerTrato(almacen)).toEqual(preferencia);
  });

  it('solo guarda el trato y el nombre, con una clave versionada', () => {
    const almacen = new AlmacenFalso();
    guardarTrato(almacen, crearPreferencia('don', 'Carlos')!);
    expect([...almacen.datos.keys()]).toEqual([CLAVE_TRATO]);
    expect(JSON.parse(almacen.datos.get(CLAVE_TRATO)!)).toEqual({ trato: 'don', nombre: 'Carlos' });
  });

  it.each([
    ['JSON dañado', '{trato:'],
    ['un texto suelto', '"Rosa"'],
    ['nulo', 'null'],
    ['un trato que no existe', '{"trato":"señora","nombre":"Rosa"}'],
    ['un nombre con números', '{"trato":"dona","nombre":"3001234567"}'],
    ['marcado en el nombre', '{"trato":"dona","nombre":"<img src=x>"}'],
  ])('al leer descarta %s (Zero Trust)', (_caso, crudo) => {
    const almacen = new AlmacenFalso();
    almacen.datos.set(CLAVE_TRATO, crudo);
    expect(leerTrato(almacen)).toBeNull();
  });

  it('borrar deja el celular sin el nombre', () => {
    const almacen = new AlmacenFalso();
    guardarTrato(almacen, crearPreferencia('dona', 'Rosa')!);
    borrarTrato(almacen);
    expect(leerTrato(almacen)).toBeNull();
    expect(almacen.datos.size).toBe(0);
  });

  it('si el navegador no deja guardar, avisa sin romper la app', () => {
    expect(guardarTrato(new AlmacenFalso(true), crearPreferencia('dona', 'Rosa')!)).toBe(false);
    expect(guardarTrato(undefined, crearPreferencia('dona', 'Rosa')!)).toBe(false);
    expect(leerTrato(undefined)).toBeNull();
    expect(() => borrarTrato(undefined)).not.toThrow();
  });
});
