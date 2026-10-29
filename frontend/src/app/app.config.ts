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

/**
 * Configuracion raiz de la aplicacion (standalone).
 *
 * Registra el router, el HttpClient con el interceptor base de Correlation-ID
 * y el Service Worker (habilitado solo fuera de modo desarrollo), que da el
 * soporte de cache y operacion offline de la PWA (Req 2, Req 18).
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([correlationIdInterceptor])),
    provideServiceWorker('ngsw-worker.js', {
      enabled: !isDevMode(),
      registrationStrategy: 'registerWhenStable:30000',
    }),
  ],
};
