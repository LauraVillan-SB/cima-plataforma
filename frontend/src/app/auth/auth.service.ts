import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/**
 * Cliente de autenticación del frontend. Solo realiza llamadas HTTP al Auth
 * Service del backend (sin lógica de negocio ni autorización en el cliente,
 * conforme a la separación de capas). La sesión se maneja por cookie HttpOnly
 * en el backend; aquí solo se refleja el estado para la UI.
 * Requisitos: 1.1, 1.8, 2.6, 2.7.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  /** Indica si hay una sesión vigente (para mostrar/ocultar vistas). */
  readonly autenticado = signal<boolean>(false);

  /** Registra un nuevo Usuario con teléfono y Clave de 4 dígitos (Req 1.1). */
  async registrar(telefono: string, clave: string): Promise<void> {
    await firstValueFrom(
      this.http.post('/api/v1/auth/registro', { telefono, clave }, { withCredentials: true }),
    );
    this.autenticado.set(true);
  }

  /** Inicia sesión con teléfono y Clave; la cookie de sesión la fija el backend. */
  async ingresar(telefono: string, clave: string): Promise<void> {
    await firstValueFrom(
      this.http.post('/api/v1/auth/ingreso', { telefono, clave }, { withCredentials: true }),
    );
    this.autenticado.set(true);
  }

  /** Restaura la sesión vigente al abrir la app, sin volver a pedir la Clave (Req 2.6). */
  async restaurarSesion(): Promise<boolean> {
    try {
      await firstValueFrom(
        this.http.get('/api/v1/auth/sesion', { withCredentials: true }),
      );
      this.autenticado.set(true);
      return true;
    } catch {
      this.autenticado.set(false);
      return false;
    }
  }

  /** Cierra la sesión en el backend (borra las cookies). */
  async salir(): Promise<void> {
    await firstValueFrom(
      this.http.post('/api/v1/auth/salir', {}, { withCredentials: true }),
    );
    this.autenticado.set(false);
  }
}
