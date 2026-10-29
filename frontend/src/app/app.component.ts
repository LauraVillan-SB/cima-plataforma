import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Componente raiz (shell) de la PWA de CIMA. Mantiene el shell ligero; las
 * vistas de dominio se cargan por el router. Usa OnPush para minimizar el
 * trabajo de deteccion de cambios (performance, Req 2).
 */
@Component({
  selector: 'cima-root',
  standalone: true,
  imports: [RouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main>
      <h1>CIMA</h1>
      <p>Escuela de Sostenibilidad e Inclusion Bolivar</p>
      <router-outlet />
    </main>
  `,
})
export class AppComponent {}
