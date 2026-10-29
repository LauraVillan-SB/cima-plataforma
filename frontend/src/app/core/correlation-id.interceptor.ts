import { HttpInterceptorFn } from '@angular/common/http';

/** Nombre del encabezado de correlacion, consistente con el backend (Req 11.1). */
export const CORRELATION_HEADER = 'X-Correlation-ID';

/**
 * Genera un UUID v4 para correlacionar la peticion de extremo a extremo.
 * Usa `crypto.randomUUID` cuando esta disponible (navegadores modernos).
 */
function generarCorrelationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  // Respaldo simple si randomUUID no esta disponible.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Interceptor base: adjunta un `X-Correlation-ID` a cada peticion saliente si
 * no viene ya establecido, para trazabilidad de extremo a extremo con el
 * backend (Req 11.1). Solo presentacion; sin logica de negocio.
 */
export const correlationIdInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.headers.has(CORRELATION_HEADER)) {
    return next(req);
  }
  const conCorrelacion = req.clone({
    setHeaders: { [CORRELATION_HEADER]: generarCorrelationId() },
  });
  return next(conCorrelacion);
};
