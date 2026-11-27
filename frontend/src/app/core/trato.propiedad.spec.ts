/**
 * Propiedad 46: la preferencia de nombre solo se conserva para su dueño.
 * Valida: Req 13.8, Req 19.9.
 *
 * Para cualquier par de Perfiles distintos A y B, cualquier preferencia válida y
 * cualquier contenido previo del almacén:
 * - al entrar A, el nombre queda solo si lo guardó A; si no, se borra;
 * - si A guardó su nombre, A lo conserva al volver a entrar y B lo borra;
 * - lo guardado nunca contiene el identificador del Perfil, solo su huella.
 *
 * Que el nombre nunca viaje al backend lo garantiza el diseño (lógica pura sin
 * HTTP); esta prueba no lo cubre.
 */
import fc from 'fast-check';

import {
  AlmacenClaveValor,
  CLAVE_TRATO,
  conservarTratoSiEsDe,
  crearPreferencia,
  duenoDelTrato,
  guardarTrato,
  huellaDePerfil,
  leerTrato,
  PreferenciaTrato,
} from './trato';

const EJECUCIONES = 200;

/** Almacén en memoria con la misma interfaz que `localStorage`. */
function almacenEnMemoria(inicial: string | null): AlmacenClaveValor {
  const datos = new Map<string, string>();
  if (inicial !== null) {
    datos.set(CLAVE_TRATO, inicial);
  }
  return {
    getItem: (clave) => datos.get(clave) ?? null,
    setItem: (clave, valor) => {
      datos.set(clave, valor);
    },
    removeItem: (clave) => {
      datos.delete(clave);
    },
  };
}

const preferenciaArb: fc.Arbitrary<PreferenciaTrato> = fc
  .record({
    trato: fc.constantFrom('don', 'dona', 'nombre'),
    nombre: fc.stringMatching(/^[a-záéíóúñ]{1,12}( [a-záéíóúñ]{1,12})?$/),
  })
  .map(({ trato, nombre }) => crearPreferencia(trato, nombre))
  .filter((p): p is PreferenciaTrato => p !== null);

const perfilesDistintosArb = fc
  .tuple(fc.uuid(), fc.uuid())
  .filter(([a, b]) => a !== b);

const huellaArb = fc.stringMatching(/^[0-9a-f]{64}$/);

/** Contenido previo arbitrario: nada, texto cualquiera o JSON con un dueño cualquiera. */
const contenidoPrevioArb: fc.Arbitrary<string | null> = fc.oneof(
  fc.constant(null),
  fc.string(),
  fc
    .record({
      trato: fc.constantFrom('don', 'dona', 'nombre', 'otro'),
      nombre: fc.string({ maxLength: 40 }),
      dueno: fc.option(fc.oneof(huellaArb, fc.string()), { nil: undefined }),
    })
    .map((dato) => JSON.stringify(dato)),
);

describe('Propiedad 46: la preferencia de nombre solo se conserva para su dueño', () => {
  it('con cualquier contenido previo, al entrar queda el nombre solo si es de quien entra', async () => {
    await fc.assert(
      fc.asyncProperty(fc.uuid(), contenidoPrevioArb, async (idPerfil, previo) => {
        const almacen = almacenEnMemoria(previo);
        const huella = await huellaDePerfil(idPerfil);
        const eraSuyo = huella !== null && duenoDelTrato(almacen) === huella;

        const conservado = conservarTratoSiEsDe(almacen, huella);

        expect(conservado).toBe(eraSuyo);
        if (!conservado) {
          expect(almacen.getItem(CLAVE_TRATO)).toBeNull();
          expect(leerTrato(almacen)).toBeNull();
        }
      }),
      { numRuns: EJECUCIONES },
    );
  });

  it('A conserva su nombre al volver a entrar y B lo borra; nunca se guarda el id', async () => {
    await fc.assert(
      fc.asyncProperty(
        perfilesDistintosArb,
        preferenciaArb,
        contenidoPrevioArb,
        async ([idA, idB], preferencia, previo) => {
          const almacen = almacenEnMemoria(previo);
          const huellaA = await huellaDePerfil(idA);
          const huellaB = await huellaDePerfil(idB);
          expect(huellaA).not.toBeNull();
          expect(huellaA).not.toBe(huellaB);

          expect(guardarTrato(almacen, preferencia, huellaA)).toBe(true);
          const guardado = almacen.getItem(CLAVE_TRATO) ?? '';
          expect(guardado).not.toContain(idA);

          expect(conservarTratoSiEsDe(almacen, huellaA)).toBe(true);
          expect(leerTrato(almacen)).toEqual(preferencia);

          expect(conservarTratoSiEsDe(almacen, huellaB)).toBe(false);
          expect(leerTrato(almacen)).toBeNull();
          expect(almacen.getItem(CLAVE_TRATO)).toBeNull();
        },
      ),
      { numRuns: EJECUCIONES },
    );
  });
});
