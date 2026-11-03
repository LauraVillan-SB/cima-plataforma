import { Routes } from '@angular/router';

/**
 * Rutas de la aplicacion. La ruta de autenticacion es el punto de entrada;
 * se incorporan los demas feature routes por dominio a medida que se
 * implementan las tareas del plan.
 */
export const routes: Routes = [
  {
    path: 'entrar',
    loadComponent: () =>
      import('./auth/auth-page.component').then((m) => m.AuthPageComponent),
    title: 'Entrar a CIMA',
  },
  { path: '', redirectTo: 'entrar', pathMatch: 'full' },
];
