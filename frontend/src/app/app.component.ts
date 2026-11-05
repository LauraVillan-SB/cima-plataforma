import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { ConnectionStatusComponent } from './shell/connection-status.component';

/**
 * Componente raiz (shell) de la PWA de CIMA. Mantiene el shell ligero; las
 * vistas de dominio se cargan por el router. Muestra el indicador de
 * conexion/sincronizacion (Req 2.9, 18.5). Usa OnPush para minimizar el
 * trabajo de deteccion de cambios (performance, Req 2).
 *
 * Encabezado con la identidad de Seguros Bolivar (logo del bundle
 * @seguros-bolivar/ui-bundle sobre el verde primario de la marca).
 */
@Component({
  selector: 'cima-root',
  standalone: true,
  imports: [RouterOutlet, ConnectionStatusComponent],
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
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.75rem 1rem;
        background: var(--sb-ui-color-primary-base, #009056);
      }
      .barra__logo {
        height: 32px;
        width: auto;
      }
      .barra__producto {
        color: #fff;
        font-weight: 700;
        letter-spacing: 0.05em;
      }
      .contenido {
        flex: 1;
      }
    `,
  ],
})
export class AppComponent {}
