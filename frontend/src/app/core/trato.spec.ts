import {
  AlmacenClaveValor,
  CLAVE_TRATO,
  MAX_NOMBRE,
  borrarTrato,
  comoLlamar,
  conservarTratoSiEsDe,
  crearPreferencia,
  duenoDelTrato,
  guardarTrato,
  huellaDePerfil,
  leerTrato,
  normalizarNombre,
} from './trato';

describe('nombre que se conserva para la misma persona', () => {
  const patricia = { trato: 'dona', nombre: 'Patricia' } as const;
  // Identificadores inventados para la prueba.
  const ID_A = '11111111-1111-4111-8111-111111111111';
  const ID_B = '22222222-2222-4222-8222-222222222222';

  it('la huella es un SHA-256 estable que no muestra el identificador', async () => {
    const a = await huellaDePerfil(ID_A);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(await huellaDePerfil(ID_A)).toBe(a);
    expect(await huellaDePerfil(ID_B)).not.toBe(a);
    expect(a).not.toContain('11111111');
  });

  it('sin criptografía o sin id no hay huella', async () => {
    expect(await huellaDePerfil(ID_A, null)).toBeNull();
    expect(await huellaDePerfil('')).toBeNull();
  });

  it('si el navegador falla al calcularla, no hay huella y el ingreso sigue', async () => {
    const falla = {
      digest: () => Promise.reject(new DOMException('no', 'NotSupportedError')),
    } as unknown as SubtleCrypto;
    expect(await huellaDePerfil(ID_A, falla)).toBeNull();
  });

  it('la misma persona conserva su nombre al volver a entrar', async () => {
    const almacen = new AlmacenFalso();
    const huella = await huellaDePerfil(ID_A);
    guardarTrato(almacen, patricia, huella);
    expect(duenoDelTrato(almacen)).toBe(huella);
    expect(conservarTratoSiEsDe(almacen, await huellaDePerfil(ID_A))).toBe(true);
    expect(leerTrato(almacen)).toEqual(patricia);
  });

  it('si entra otra persona, el nombre se borra antes de mostrarlo', async () => {
    const almacen = new AlmacenFalso();
    guardarTrato(almacen, patricia, await huellaDePerfil(ID_A));
    expect(conservarTratoSiEsDe(almacen, await huellaDePerfil(ID_B))).toBe(false);
    expect(leerTrato(almacen)).toBeNull();
  });

  it('un nombre sin dueño, con dueño alterado o sin huella al entrar se borra', async () => {
    const huella = await huellaDePerfil(ID_A);
    const sinDueno = new AlmacenFalso();
    guardarTrato(sinDueno, patricia);
    expect(conservarTratoSiEsDe(sinDueno, huella)).toBe(false);

    const alterado = new AlmacenFalso();
    alterado.setItem(CLAVE_TRATO, JSON.stringify({ ...patricia, dueno: 'cualquier-cosa' }));
    expect(duenoDelTrato(alterado)).toBeNull();
    expect(conservarTratoSiEsDe(alterado, huella)).toBe(false);

    const conDueno = new AlmacenFalso();
    guardarTrato(conDueno, patricia, huella);
    expect(conservarTratoSiEsDe(conDueno, null)).toBe(false);
  });

  it('una huella inválida no se guarda como dueño', () => {
    const almacen = new AlmacenFalso();
    guardarTrato(almacen, patricia, 'no-es-una-huella');
    expect(duenoDelTrato(almacen)).toBeNull();
  });
});

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
