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
  { path: 'inicio', redirectTo: 'aprendizaje', pathMatch: 'full' },
  {
    path: 'aprendizaje',
    loadComponent: () =>
      import('./aprendizaje/learning-page.component').then(
        (m) => m.LearningPageComponent,
      ),
    title: 'Aprendizaje - CIMA',
  },
  {
    path: 'aprendizaje/leccion/:pathId/:capsuleId',
    loadComponent: () =>
      import('./aprendizaje/lesson-page.component').then((m) => m.LessonPageComponent),
    title: 'Lección - CIMA',
  },
  {
    path: 'mi-ruta',
    loadComponent: () =>
      import('./aprendizaje/my-route-page.component').then((m) => m.MyRoutePageComponent),
    title: 'Mi ruta - CIMA',
  },
  {
    path: 'reconocimientos',
    loadComponent: () =>
      import('./gamificacion/recognitions-page.component').then(
        (m) => m.RecognitionsPageComponent,
      ),
    title: 'Reconocimientos - CIMA',
  },
  {
    path: 'ranking',
    loadComponent: () =>
      import('./gamificacion/ranking-page.component').then((m) => m.RankingPageComponent),
    title: 'Ranking - CIMA',
  },
  {
    path: 'evaluacion/:rutaId',
    loadComponent: () =>
      import('./evaluacion/assessment-page.component').then(
        (m) => m.AssessmentPageComponent,
      ),
    title: 'Evaluación - CIMA',
  },
  { path: '', redirectTo: 'entrar', pathMatch: 'full' },
  { path: '**', redirectTo: 'entrar' },
];
