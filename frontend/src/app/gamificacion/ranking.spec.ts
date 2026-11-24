import { nombreEnRanking } from './ranking';

/**
 * Pruebas del nombre en el ranking: el propio solo en la fila propia.
 * Feature: cima-plataforma
 */
describe('nombreEnRanking', () => {
  it('en la fila propia muestra el nombre del celular con "(usted)"', () => {
    expect(nombreEnRanking('Participante 7599', true, 'doña Patricia')).toBe(
      'doña Patricia (usted)',
    );
  });

  it('en la fila propia sin nombre guardado deja el alias con "(usted)"', () => {
    expect(nombreEnRanking('Participante 7599', true, null)).toBe('Participante 7599 (usted)');
    expect(nombreEnRanking('Participante 7599', true, '  ')).toBe('Participante 7599 (usted)');
  });

  it('en las filas de otras personas siempre muestra el alias, nunca el nombre propio', () => {
    expect(nombreEnRanking('Participante 8C86', false, 'doña Patricia')).toBe('Participante 8C86');
  });
});
