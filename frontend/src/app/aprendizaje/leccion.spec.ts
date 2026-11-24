import { abrirTextoDeEntrada, iconoDeEstado } from './leccion';
import { iconoTema } from './temas';

/**
 * Pruebas de la presentación de la lección: acordeón "¿Quiere conocer más?" e íconos.
 * Feature: cima-plataforma
 */
describe('abrirTextoDeEntrada', () => {
  const base = { tieneVideo: false, resumen: null, puntosClave: [] as string[] };

  it('arranca cerrado si hay video, resumen o puntos clave', () => {
    expect(abrirTextoDeEntrada({ ...base, tieneVideo: true })).toBe(false);
    expect(abrirTextoDeEntrada({ ...base, resumen: 'Cuide el suelo.' })).toBe(false);
    expect(abrirTextoDeEntrada({ ...base, puntosClave: ['Ahorre cada semana.'] })).toBe(false);
  });

  it('arranca abierto si no hay nada más que leer, para no dejar la lección vacía', () => {
    expect(abrirTextoDeEntrada(base)).toBe(true);
    expect(abrirTextoDeEntrada({ ...base, resumen: '   ' })).toBe(true);
    expect(abrirTextoDeEntrada({ ...base, resumen: undefined })).toBe(true);
  });
});

describe('iconoDeEstado', () => {
  it('da un ícono por cada estado de la cápsula', () => {
    expect(iconoDeEstado('completed')).toBe('fa-check');
    expect(iconoDeEstado('next')).toBe('fa-play');
    expect(iconoDeEstado('pending')).toBe('fa-lock');
  });

  it.each(['otro', '', 'toString', '__proto__'])(
    'un estado desconocido se muestra como pendiente: %s',
    (estado) => {
      expect(iconoDeEstado(estado)).toBe('fa-lock');
    },
  );
});

describe('iconoTema', () => {
  it('da un ícono por cada tema y uno de respaldo para los demás', () => {
    expect(iconoTema('finanzas')).toBe('fa-piggy-bank');
    expect(iconoTema('gestion_riesgos')).toBe('fa-shield-halved');
    expect(iconoTema('adaptacion_clima')).toBe('fa-cloud-sun-rain');
    expect(iconoTema('constructor')).toBe('fa-book-open');
    expect(iconoTema('')).toBe('fa-book-open');
  });
});
