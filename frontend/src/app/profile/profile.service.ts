import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/**
 * Perfil tal como lo devuelve el backend (DTO de salida con PII enmascarada:
 * el teléfono llega con solo los últimos 4 dígitos visibles, Req 9.4). El
 * frontend nunca recibe ni muestra el teléfono completo.
 */
export interface Perfil {
  readonly id: string;
  readonly phone: string;
  readonly activity_type: string;
  readonly geo_zone: string;
}

/**
 * Datos para actualizar el Perfil propio. No lleva el celular: es la identidad
 * de ingreso, no se edita por aquí y el cliente solo lo conoce enmascarado
 * (Req 9.4); el backend rechaza un `phone` en la actualización.
 */
export interface PerfilActualizacion {
  readonly activity_type: string;
  readonly geo_zone: string;
}

/**
 * Cliente del Profile Service del backend. Solo realiza llamadas HTTP; sin
 * lógica de negocio ni autorización en el cliente (la titularidad del recurso
 * la verifica el backend, anti-BOLA, Req 9.6). La sesión viaja por la cookie
 * HttpOnly. Requisitos: 9.1, 9.4, 9.5, 9.6.
 */
@Injectable({ providedIn: 'root' })
export class ProfileService {
  private readonly http = inject(HttpClient);

  /** Obtiene el Perfil del Usuario autenticado (`GET /api/v1/perfiles/me`). */
  async obtenerMiPerfil(): Promise<Perfil> {
    return firstValueFrom(
      this.http.get<Perfil>('/api/v1/perfiles/me', { withCredentials: true }),
    );
  }

  /**
   * Actualiza el Perfil propio (`PUT /api/v1/perfiles/{id}`). El backend
   * verifica que el recurso pertenezca al Usuario autenticado antes de aplicar
   * el cambio; el `id` solo identifica el recurso, no otorga permiso.
   */
  async actualizar(id: string, datos: PerfilActualizacion): Promise<Perfil> {
    return firstValueFrom(
      this.http.put<Perfil>(`/api/v1/perfiles/${id}`, datos, { withCredentials: true }),
    );
  }
}
