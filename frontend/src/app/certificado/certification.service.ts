import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/**
 * Certificado tal como lo entrega el backend (`/api/v1/certificados`). Nunca trae el
 * identificador interno del titular ni su celular completo: el celular llega
 * enmascarado desde el servidor (Req 6.3, 9.4).
 */
export interface Certificado {
  readonly id: string;
  readonly path_id: string;
  readonly verification_code: string;
  readonly issued_at: string;
  readonly path_title: string | null;
  readonly holder_phone_masked: string | null;
}

/**
 * Cliente del Certification Service. Solo realiza llamadas HTTP: la emisión exige ruta
 * completa y evaluación aprobada, y eso lo verifica el backend con la identidad de la
 * sesión (anti-BOLA); el cliente no decide nada. La sesión viaja en la cookie HttpOnly.
 * Requisitos: 6.1–6.7.
 */
@Injectable({ providedIn: 'root' })
export class CertificationService {
  private readonly http = inject(HttpClient);

  /**
   * Obtiene el Certificado de una ruta (`POST /api/v1/certificados`). Es idempotente:
   * si ya se emitió, el backend devuelve el mismo, así que sirve para verlo de nuevo
   * (Req 6.4).
   */
  async obtener(rutaId: string): Promise<Certificado> {
    return firstValueFrom(
      this.http.post<Certificado>(
        '/api/v1/certificados',
        { path_id: rutaId },
        { withCredentials: true },
      ),
    );
  }
}
