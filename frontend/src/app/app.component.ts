import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { AuthService } from './auth/auth.service';
import { GamificationService } from './gamificacion/gamification.service';
import { ConnectionStatusComponent } from './shell/connection-status.component';

/**
 * Componente raiz (shell) de la PWA de CIMA. Encabezado verde oscuro con el
 * logo de Seguros Bolivar, chips de racha, puntos y nivel (datos reales del
 * backend), navegacion principal y pie institucional. En la pantalla de
 * entrada solo se muestra el logo. Usa OnPush para minimizar el trabajo de
 * deteccion de cambios (Req 2). Muestra el indicador de conexion (Req 2.9, 18.5).
 */
@Component({
  selector: 'cima-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ConnectionStatusComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a class="saltar" href="#contenido">Saltar al contenido</a>
    <header class="barra">
      <div class="barra__fila">
        <a routerLink="/aprendizaje" class="barra__marca" aria-label="CIMA, ir al inicio">
          <img
            src="logos/sb-logo-horizontal-white.svg"
            alt="Seguros Bolívar"
            width="150"
            height="40"
          />
          <span class="barra__producto">CIMA</span>
        </a>
        @if (conSesion()) {
          <ul class="chips" aria-label="Tu avance">
            @if (resumen(); as r) {
              <li class="chip" title="Días seguidos aprendiendo">
                <span aria-hidden="true">🔥</span> {{ r.streak_days }}
                <span class="solo-lector">días seguidos</span>
              </li>
              <li class="chip" title="Tus puntos">
                <span aria-hidden="true">★</span> {{ r.total_points }}
                <span class="solo-lector">puntos</span>
              </li>
              <li class="chip chip--nivel" title="Tu nivel">{{ r.level.name }}</li>
            }
          </ul>
          <button type="button" class="salir" [disabled]="saliendo()" (click)="salir()">
            Salir
          </button>
        }
      </div>
      @if (conSesion()) {
        <nav class="nav" aria-label="Principal">
          <a routerLink="/aprendizaje" routerLinkActive="activo" [routerLinkActiveOptions]="{ exact: true }">Microcápsulas</a>
          <a routerLink="/mi-ruta" routerLinkActive="activo">Mi ruta</a>
          <a routerLink="/reconocimientos" routerLinkActive="activo">Reconocimientos</a>
          <a routerLink="/ranking" routerLinkActive="activo">Ranking</a>
        </nav>
      }
    </header>
    <cima-connection-status />
    <main id="contenido" class="contenido">
      <router-outlet />
    </main>
    <footer class="pie">
      <img src="logos/sb-logo-horizontal-white.svg" alt="Seguros Bolívar" width="120" height="32" />
      <p>
        CIMA es la plataforma educativa de la Escuela de Sostenibilidad e Inclusión de
        Seguros Bolívar. Aquí aprendes; no se hacen pagos ni se expiden pólizas.
      </p>
    </footer>
  `,
  styles: [
    `
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100svh;
      }
      .saltar {
        position: absolute;
        left: -999px;
      }
      .saltar:focus {
        left: 0.5rem;
        top: 0.5rem;
        z-index: 10;
        background: var(--cima-dorado);
        color: var(--cima-texto);
        padding: 0.5rem 1rem;
      }
      .barra {
        background: var(--cima-verde-oscuro);
        color: #fff;
      }
      .barra__fila {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
      }
      .barra__marca {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        color: #fff;
        text-decoration: none;
      }
      .barra__marca img {
        height: 32px;
        width: auto;
      }
      .barra__producto {
        font-weight: 700;
        letter-spacing: 0.08em;
        color: var(--cima-dorado);
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        min-height: 36px;
        padding: 0 0.85rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.14);
        font-weight: 700;
        font-size: 1rem;
      }
      .chip--nivel {
        background: var(--cima-dorado);
        color: var(--cima-texto);
      }
      .solo-lector {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }
      .salir {
        border: 2px solid #fff;
        background: transparent;
        color: #fff;
        border-radius: 999px;
        padding: 0 1rem;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
      }
      .nav {
        display: flex;
        gap: 0.25rem;
        overflow-x: auto;
        padding: 0 0.75rem;
        background: rgba(0, 0, 0, 0.18);
      }
      .nav a {
        display: inline-flex;
        align-items: center;
        padding: 0 1rem;
        color: #fff;
        text-decoration: none;
        font-weight: 600;
        white-space: nowrap;
        border-bottom: 4px solid transparent;
      }
      .nav a.activo {
        border-bottom-color: var(--cima-dorado);
        color: var(--cima-dorado);
      }
      .contenido {
        flex: 1;
      }
      .pie {
        background: var(--cima-verde-oscuro);
        color: #fff;
        padding: 1.5rem 1rem;
        text-align: center;
        font-size: 0.95rem;
      }
      .pie p {
        max-width: 560px;
        margin: 0.75rem auto 0;
      }
    `,
  ],
})
export class AppComponent {
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly gamificacion = inject(GamificationService);

  readonly resumen = this.gamificacion.resumen;
  readonly conSesion = signal<boolean>(false);
  readonly saliendo = signal<boolean>(false);

  constructor() {
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => void this.alNavegar(e.urlAfterRedirects));
  }

  /** Muestra el menú fuera de la entrada y carga los chips si faltan. */
  private async alNavegar(url: string): Promise<void> {
    const enEntrada = url.startsWith('/entrar');
    this.conSesion.set(!enEntrada);
    if (!enEntrada && this.resumen() === null) {
      try {
        await this.gamificacion.cargarResumen();
      } catch {
        // Sin resumen no se muestran chips; las vistas manejan su propio error.
      }
    }
  }

  /** Cierra la sesión, limpia el estado de gamificación y vuelve a la entrada. */
  async salir(): Promise<void> {
    this.saliendo.set(true);
    try {
      await this.auth.salir();
    } finally {
      this.gamificacion.limpiar();
      this.saliendo.set(false);
      await this.router.navigate(['/entrar']);
    }
  }
}
