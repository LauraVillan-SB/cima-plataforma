import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';
import { ConnectionStatusComponent } from './shell/connection-status.component';
import { UserMenuComponent } from './shell/user-menu.component';

/**
 * Componente raiz (shell) de la PWA de CIMA. Mantiene el shell ligero; las
 * vistas de dominio se cargan por el router. Muestra el indicador de
 * conexion/sincronizacion (Req 2.9, 18.5). Usa OnPush para minimizar el
 * trabajo de deteccion de cambios (performance, Req 2).
 *
 * Encabezado con la identidad de Seguros Bolivar (logo del bundle
 * @seguros-bolivar/ui-bundle sobre el verde primario de la marca) y, cuando
 * hay sesion, el menu de la cuenta (quien soy, perfil, cambiar clave y salir).
 * Al abrir la app se intenta restaurar la sesion vigente sin pedir la Clave
 * (Req 2.6); la sesion vive en la cookie HttpOnly del backend.
 */
@Component({
  selector: 'cima-root',
  imports: [RouterOutlet, ConnectionStatusComponent, UserMenuComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="barra">
      <img
        class="barra__logo"
        src="logos/sb-logo-horizontal-white.svg"
        alt="Seguros Bolívar"
        width="150"
        height="40"
      />
      <span class="barra__producto">CIMA</span>
      @if (auth.autenticado()) {
        <cima-user-menu />
      }
    </header>
    <cima-connection-status />
    <main class="contenido">
      <router-outlet />
    </main>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100svh;
        background: var(--sb-ui-color-grayscale-L300, #f5f5f5);
      }
      .barra {
        position: relative;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.75rem 1rem;
        padding: 0.75rem 1rem;
        background: var(--sb-ui-color-primary-base, #009056);
      }
      .barra__logo {
        height: 32px;
        width: auto;
      }
      /* Texto grande y en negrita: el blanco sobre este verde cumple AA (>= 3:1). */
      .barra__producto {
        margin-inline-end: auto;
        color: #fff;
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: 0.05em;
      }
      .contenido {
        flex: 1;
      }
    `,
  ],
})
export class AppComponent {
  protected readonly auth = inject(AuthService);

  constructor() {
    // Si la cookie de sesion sigue vigente, la app lo sabe sin pedir la Clave.
    void this.auth.restaurarSesion();
  }
}
