/** Configuracion de Jest para pruebas de logica pura del frontend (Tarea 2). */
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  // `scripts/` tiene herramientas de build en CommonJS (p. ej. presupuesto de carga).
  roots: ['<rootDir>/src', '<rootDir>/scripts'],
  testMatch: ['**/*.spec.ts', '**/*.spec.cjs'],
  moduleFileExtensions: ['ts', 'js', 'cjs', 'json'],
  transform: {
    '^.+\\.ts$': ['ts-jest', { tsconfig: 'tsconfig.spec.json' }],
  },
};
