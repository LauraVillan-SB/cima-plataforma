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
  {
    path: 'inicio',
    loadComponent: () =>
      import('./home/home-page.component').then((m) => m.HomePageComponent),
    title: 'CIMA',
  },
  {
    path: 'aprendizaje',
    loadComponent: () =>
      import('./aprendizaje/learning-page.component').then(
        (m) => m.LearningPageComponent,
      ),
    title: 'Aprendizaje - CIMA',
  },
  {
    path: 'perfil',
    loadComponent: () =>
      import('./profile/profile-page.component').then((m) => m.ProfilePageComponent),
    title: 'Mi perfil - CIMA',
  },
  {
    path: 'clave',
    loadComponent: () =>
      import('./auth/change-password-page.component').then(
        (m) => m.ChangePasswordPageComponent,
      ),
    title: 'Cambiar mi clave - CIMA',
  },
  {
    path: 'evaluacion/:rutaId',
    loadComponent: () =>
      import('./evaluacion/assessment-page.component').then(
        (m) => m.AssessmentPageComponent,
      ),
    title: 'Evaluación - CIMA',
  },
  {
    path: 'asistente',
    loadComponent: () =>
      import('./chat/chat-page.component').then((m) => m.ChatPageComponent),
    title: 'Asistente - CIMA',
  },
  {
    path: 'conversion/:rutaId',
    loadComponent: () =>
      import('./conversion/conversion-page.component').then(
        (m) => m.ConversionPageComponent,
      ),
    title: 'Microseguros - CIMA',
  },
  {
    path: 'logros',
    loadComponent: () =>
      import('./gamificacion/gamification-page.component').then(
        (m) => m.GamificationPageComponent,
      ),
    title: 'Tus logros - CIMA',
  },
  { path: '', redirectTo: 'entrar', pathMatch: 'full' },
  { path: '**', redirectTo: 'entrar' },
];
