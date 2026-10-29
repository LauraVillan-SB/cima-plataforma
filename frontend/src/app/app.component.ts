import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { ConnectionStatusComponent } from './shell/connection-status.component';

/**
 * Componente raiz (shell) de la PWA de CIMA. Mantiene el shell ligero; las
 * vistas de dominio se cargan por el router. Muestra de forma persistente el
 * indicador de conexion/sincronizacion (Req 2.9, 18.5). Usa OnPush para
 * minimizar el trabajo de deteccion de cambios (performance, Req 2).
 */
@Component({
  selector: 'cima-root',
  standalone: true,
  imports: [RouterOutlet, ConnectionStatusComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header>
      <h1>CIMA</h1>
      <cima-connection-status />
    </header>
    <main>
      <router-outlet />
    </main>
  `,
})
export class AppComponent {}
