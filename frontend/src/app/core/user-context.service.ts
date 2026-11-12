import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';

import { AuthService } from '../auth/auth.service';
import { etiquetaActividad, fraseActividad } from '../profile/perfil';
import { ProfileService, type Perfil } from '../profile/profile.service';

/**
 * Contexto de la persona con sesión iniciada: guarda su Perfil para que el
 * menú del encabezado y el inicio puedan decir quién es ("tu cultivo de café")
 * sin que cada pantalla vuelva a pedirlo.
 *
 * Solo presentación. El Perfil llega del backend con el teléfono ya enmascarado
 * (solo los últimos 4 dígitos, Req 9.4): aquí nunca se maneja el número
 * completo y nada se guarda en el navegador (ni `localStorage` ni
 * `sessionStorage`); vive solo en memoria mientras dura la pestaña.
 */
@Injectable({ providedIn: 'root' })
export class UserContextService {
  private readonly auth = inject(AuthService);
  private readonly profiles = inject(ProfileService);

  /** Perfil de la persona con sesión; `null` si no hay sesión o aún no lo crea. */
  readonly perfil = signal<Perfil | null>(null);

  /** `true` mientras se consulta el Perfil al iniciar sesión. */
  readonly cargando = signal<boolean>(false);

  /** Etiqueta corta de su actividad ("Café"); vacía si no hay Perfil. */
  readonly actividadEtiqueta = computed(() => {
    const p = this.perfil();
    return p ? etiquetaActividad(p.activity_type) : '';
  });

  /** Frase para saludar ("tu cultivo de café"); vacía si no hay Perfil. */
  readonly actividadFrase = computed(() => {
    const p = this.perfil();
    return p ? fraseActividad(p.activity_type) : '';
  });

  constructor() {
    // Al iniciar sesión se trae el Perfil; al salir se olvida. El efecto solo
    // depende de `autenticado`: el resto se ejecuta sin rastrearse.
    effect(() => {
      const hayDatosDeSesion = this.auth.autenticado();
      untracked(() => {
        if (hayDatosDeSesion) {
          void this.cargar();
        } else {
          this.perfil.set(null);
        }
      });
    });
  }

  /** Reemplaza el Perfil en memoria (p. ej. tras guardarlo en la pantalla de Perfil). */
  establecer(perfil: Perfil | null): void {
    this.perfil.set(perfil);
  }

  /** Consulta el Perfil propio; si todavía no existe (404) queda en `null`. */
  private async cargar(): Promise<void> {
    this.cargando.set(true);
    try {
      this.perfil.set(await this.profiles.obtenerMiPerfil());
    } catch {
      // Sin Perfil aún (404) o error de red: el saludo cae al texto neutro.
      // El detalle lo registra el backend; aquí no se muestra nada técnico.
      this.perfil.set(null);
    } finally {
      this.cargando.set(false);
    }
  }
}
