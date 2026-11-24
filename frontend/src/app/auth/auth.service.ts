import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { almacenDelNavegador, vaciarCachesDeDatos } from '../core/limpieza-local';
import { almacenLocal, conservarTratoSiEsDe, huellaDePerfil } from '../core/trato';

/** Lo que el backend devuelve al entrar, registrarse o restaurar la sesión (solo se usa el id). */
interface SesionRespuesta {
  readonly id: string;
}

/**
 * Vacía los datos de la API que el Service Worker dejó en el dispositivo cuando
 * la sesión cambia de manos (celular compartido). Ver `core/limpieza-local.ts`.
 *
 * No borra cómo quiere la persona que le digan ("doña Rosa"): ese nombre se
 * decide al entrar, según quién entra (`conservarTratoSiEsDe` en `core/trato.ts`).
 * Sin sesión la app no lo muestra.
 */
export function limpiarDatosLocales(): Promise<number> {
  return vaciarCachesDeDatos(almacenDelNavegador());
}

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

  /**
   * Huella (SHA-256) del Perfil con sesión, para marcar de quién es el nombre que
   * se guarda en el celular. Nunca se envía al servidor; `null` sin sesión.
   */
  readonly huellaSesion = signal<string | null>(null);

  /**
   * Registra un nuevo Usuario con teléfono y Clave de 4 dígitos (Req 1.1). El
   * backend exige la doble confirmación de la Clave (Req 1.3), por eso se envía
   * `confirmacion_clave`; sin ella responde 422 y nadie podría crear su cuenta.
   */
  async registrar(telefono: string, clave: string, confirmacionClave: string): Promise<void> {
    const sesion = await firstValueFrom(
      this.http.post<SesionRespuesta>(
        '/api/v1/auth/registro',
        { telefono, clave, confirmacion_clave: confirmacionClave },
        { withCredentials: true },
      ),
    );
    // Una cuenta nueva no debe ver lo que dejó en caché otra sesión del dispositivo.
    await limpiarDatosLocales();
    await this.prepararTrato(sesion);
    this.autenticado.set(true);
  }

  /**
   * Cambia la Clave del Usuario autenticado (`PUT /api/v1/auth/clave`). Exige la
   * Clave actual y la nueva con su confirmación; la verificación la hace el
   * backend (Req 1.14). Responde 204 sin cuerpo.
   */
  async cambiarClave(
    claveActual: string,
    claveNueva: string,
    confirmacionClaveNueva: string,
  ): Promise<void> {
    await firstValueFrom(
      this.http.put(
        '/api/v1/auth/clave',
        {
          clave_actual: claveActual,
          clave_nueva: claveNueva,
          confirmacion_clave_nueva: confirmacionClaveNueva,
        },
        { withCredentials: true },
      ),
    );
  }

  /** Inicia sesión con teléfono y Clave; la cookie de sesión la fija el backend. */
  async ingresar(telefono: string, clave: string): Promise<void> {
    const sesion = await firstValueFrom(
      this.http.post<SesionRespuesta>(
        '/api/v1/auth/ingreso',
        { telefono, clave },
        { withCredentials: true },
      ),
    );
    // Quien entra no debe ver lo que dejó en caché otra sesión del dispositivo.
    await limpiarDatosLocales();
    // El nombre guardado se conserva solo si es de quien entra; si no, se borra
    // ANTES de marcar la sesión, así nunca se alcanza a mostrar el de otra persona.
    await this.prepararTrato(sesion);
    this.autenticado.set(true);
  }

  /** Restaura la sesión vigente al abrir la app, sin volver a pedir la Clave (Req 2.6). */
  async restaurarSesion(): Promise<boolean> {
    let sesion: SesionRespuesta;
    try {
      sesion = await firstValueFrom(
        this.http.get<SesionRespuesta>('/api/v1/auth/sesion', { withCredentials: true }),
      );
    } catch {
      this.autenticado.set(false);
      return false;
    }
    // Se revisa el nombre igual que al entrar, por si el celular cambió de manos.
    await this.prepararTrato(sesion);
    this.autenticado.set(true);
    return true;
  }

  /**
   * Cierra la sesión en el backend (borra las cookies) y vacía los datos que el
   * Service Worker dejó en el dispositivo. La limpieza y el cambio de estado van
   * en `finally`: sin conexión el `POST /salir` falla, pero igual no deben quedar
   * datos de esta sesión a la vista del siguiente que use el celular.
   */
  async salir(): Promise<void> {
    try {
      await firstValueFrom(
        this.http.post('/api/v1/auth/salir', {}, { withCredentials: true }),
      );
    } finally {
      await limpiarDatosLocales();
      this.huellaSesion.set(null);
      this.autenticado.set(false);
    }
  }

  /** Calcula la huella de quien entró y deja el nombre guardado solo si es suyo. */
  private async prepararTrato(sesion: SesionRespuesta | null | undefined): Promise<void> {
    const id = typeof sesion?.id === 'string' ? sesion.id : '';
    const huella = await huellaDePerfil(id);
    conservarTratoSiEsDe(almacenLocal(), huella);
    this.huellaSesion.set(huella);
  }
}
