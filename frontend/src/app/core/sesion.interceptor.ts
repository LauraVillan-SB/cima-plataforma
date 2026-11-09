import {
  HttpContextToken,
  HttpErrorResponse,
  HttpEventType,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import {
  Observable,
  catchError,
  filter,
  finalize,
  map,
  of,
  shareReplay,
  switchMap,
  take,
  throwError,
} from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { RUTA_REFRESCO, debeIntentarRefresco } from './sesion';

/** Marca una petición que ya se repitió tras renovar, para no repetirla otra vez. */
const REINTENTADA = new HttpContextToken<boolean>(() => false);

/**
 * Refresco en curso compartido: si varias peticiones reciben 403 a la vez, todas
 * esperan el mismo `POST /refresco` en lugar de lanzar uno cada una.
 */
let refrescoEnCurso: Observable<boolean> | null = null;

function refrescar(next: HttpHandlerFn): Observable<boolean> {
  if (!refrescoEnCurso) {
    // Se envía con `next` (el resto de la cadena), así no vuelve a pasar por este
    // interceptor. Las cookies HttpOnly viajan solas con `withCredentials`.
    const peticion = new HttpRequest('POST', RUTA_REFRESCO, {}, { withCredentials: true });
    refrescoEnCurso = next(peticion).pipe(
      filter((evento) => evento.type === HttpEventType.Response),
      take(1),
      map(() => true),
      // Cualquier fallo del refresco significa que ya no hay sesión que renovar.
      catchError(() => of(false)),
      finalize(() => {
        refrescoEnCurso = null;
      }),
      shareReplay(1),
    );
  }
  return refrescoEnCurso;
}

/**
 * Renueva la sesión cuando el access token venció (Tarea 7.4, Req 1.14, 2.6).
 *
 * El backend mantiene viva la sesión mientras haya actividad y la invalida tras
 * 30 min sin ella. Si una petición a la API responde 403 porque el access venció,
 * se intenta `POST /api/v1/auth/refresco` una sola vez y se repite la petición.
 * Si el refresco falla, la sesión expiró: se marca como cerrada y se lleva a la
 * pantalla de entrada. La regla de cuándo intentarlo está en `sesion.ts`. Solo
 * presentación: la decisión de si la sesión vale la toma siempre el backend.
 */
export const sesionInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return next(req).pipe(
    catchError((error: unknown) => {
      if (
        !(error instanceof HttpErrorResponse) ||
        !debeIntentarRefresco(req.url, error.status, req.context.get(REINTENTADA))
      ) {
        return throwError(() => error);
      }
      return refrescar(next).pipe(
        switchMap((renovada) => {
          if (!renovada) {
            auth.autenticado.set(false);
            void router.navigate(['/entrar']);
            return throwError(() => error);
          }
          return next(req.clone({ context: req.context.set(REINTENTADA, true) }));
        }),
      );
    }),
  );
};
