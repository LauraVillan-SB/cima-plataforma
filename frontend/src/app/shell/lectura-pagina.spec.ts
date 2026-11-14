import * as fc from 'fast-check';

import { bloquesALeer } from './lectura-pagina';

/**
 * Pruebas de la lógica pura del lector de la página (Req 13.4, 14.3).
 * Feature: cima-plataforma
 */
interface Nodo {
  readonly id: string;
  readonly texto: string;
  readonly hijos: readonly string[];
}

const texto = (n: Nodo) => n.texto;
const contiene = (padre: Nodo, hijo: Nodo) => padre.hijos.includes(hijo.id);

describe('bloquesALeer', () => {
  it('conserva el orden de la página', () => {
    const nodos: Nodo[] = [
      { id: 'h1', texto: 'Título', hijos: [] },
      { id: 'p1', texto: 'Primer párrafo', hijos: [] },
      { id: 'p2', texto: 'Segundo párrafo', hijos: [] },
    ];
    expect(bloquesALeer(nodos, texto, contiene).map((n) => n.id)).toEqual(['h1', 'p1', 'p2']);
  });

  it('no repite: si un bloque contiene a otro, lee solo el de adentro', () => {
    const nodos: Nodo[] = [
      { id: 'li', texto: 'Ahorra cada semana', hijos: ['p'] },
      { id: 'p', texto: 'Ahorra cada semana', hijos: [] },
    ];
    expect(bloquesALeer(nodos, texto, contiene).map((n) => n.id)).toEqual(['p']);
  });

  it('salta los bloques vacíos o solo con espacios', () => {
    const nodos: Nodo[] = [
      { id: 'a', texto: '   ', hijos: [] },
      { id: 'b', texto: '', hijos: [] },
      { id: 'c', texto: 'Hola', hijos: [] },
    ];
    expect(bloquesALeer(nodos, texto, contiene).map((n) => n.id)).toEqual(['c']);
  });

  it('nunca deja un bloque que contenga a otro seleccionado ni uno sin texto', () => {
    const arbitrario = fc
      .array(fc.record({ texto: fc.string({ maxLength: 20 }), padre: fc.nat() }), { maxLength: 15 })
      .map((datos) =>
        datos.map((d, i) => ({
          id: String(i),
          texto: d.texto,
          // Un nodo solo puede tener como padre a uno anterior, como en el DOM.
          padre: i === 0 ? null : String(d.padre % i),
        })),
      );
    fc.assert(
      fc.property(arbitrario, (planos) => {
        const nodos: Nodo[] = planos.map((n) => ({
          id: n.id,
          texto: n.texto,
          hijos: planos.filter((h) => h.padre === n.id).map((h) => h.id),
        }));
        const elegidos = bloquesALeer(nodos, texto, contiene);
        return elegidos.every(
          (n) => n.texto.trim() !== '' && !nodos.some((o) => o !== n && contiene(n, o)),
        );
      }),
      { numRuns: 200 },
    );
  });
});
