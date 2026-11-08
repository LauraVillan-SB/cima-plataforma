import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Opción de microseguro que se le presenta al Usuario (sin precio). */
export interface OpcionMicroseguro {
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion: string;
}

/** Oferta para una ruta: de 0 a 5 opciones según la actividad del Perfil (Req 5.4, 5.8). */
export interface OfertaMicroseguros {
  readonly path_id: string;
  readonly activity_type: string;
  readonly options: readonly OpcionMicroseguro[];
}

/** Confirmación de que se registró el interés del Usuario (Req 5.5). */
export interface IntencionRegistrada {
  readonly id: string;
  readonly path_id: string;
  readonly option_code: string;
  readonly registered: boolean;
}

/**
 * Cliente del Conversion Service. CIMA solo educa y mide interés: aquí no hay
 * pagos ni emisión de pólizas, únicamente el registro de la intención. El
 * titular se resuelve por la cookie HttpOnly, por eso no se envía `profile_id`
 * (anti-BOLA). Requisitos: 5.4, 5.5, 5.6, 5.8.
 */
@Injectable({ providedIn: 'root' })
export class ConversionService {
  private readonly http = inject(HttpClient);

  /** `GET /api/v1/conversion/microseguros/{rutaId}` */
  async obtenerOferta(rutaId: string): Promise<OfertaMicroseguros> {
    return firstValueFrom(
      this.http.get<OfertaMicroseguros>(
        `/api/v1/conversion/microseguros/${encodeURIComponent(rutaId)}`,
        { withCredentials: true },
      ),
    );
  }

  /**
   * `POST /api/v1/conversion/intenciones/{rutaId}`. El `client_event_id` hace el
   * registro idempotente: reenviar el mismo valor no crea una intención nueva.
   */
  async registrarIntencion(
    rutaId: string,
    clientEventId: string,
    optionCode: string,
  ): Promise<IntencionRegistrada> {
    return firstValueFrom(
      this.http.post<IntencionRegistrada>(
        `/api/v1/conversion/intenciones/${encodeURIComponent(rutaId)}`,
        { client_event_id: clientEventId, option_code: optionCode },
        { withCredentials: true },
      ),
    );
  }
}
