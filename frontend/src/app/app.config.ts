import {
  ApplicationConfig,
  isDevMode,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { provideServiceWorker } from '@angular/service-worker';

import { routes } from './app.routes';
import { correlationIdInterceptor } from './core/correlation-id.interceptor';
import { sesionInterceptor } from './core/sesion.interceptor';

/**
 * Configuracion raiz de la aplicacion (standalone).
 *
 * Registra el router, el HttpClient con sus interceptores y el Service Worker
 * (habilitado solo fuera de modo desarrollo), que da el soporte de cache y
 * operacion offline de la PWA (Req 2, Req 18). El de sesion va primero: el
 * refresco que lanza recorre el resto de la cadena y asi tambien lleva su
 * Correlation-ID (Req 11.1).
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([sesionInterceptor, correlationIdInterceptor])),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
