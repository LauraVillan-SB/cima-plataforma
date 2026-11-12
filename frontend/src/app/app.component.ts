import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';
import { GamificationService } from './gamificacion/gamification.service';
import { ConnectionStatusComponent } from './shell/connection-status.component';
import { UserMenuComponent } from './shell/user-menu.component';

/**
 * Componente raiz (shell) de la PWA de CIMA. Encabezado verde oscuro con el
 * logo de Seguros Bolivar; con sesion muestra los chips de racha, puntos y
 * nivel (datos reales del backend), el menu de la cuenta (perfil, cambiar clave
 * y salir), la navegacion principal y el pie institucional. Al abrir la app se
 * intenta restaurar la sesion vigente sin pedir la Clave (Req 2.6); la sesion
 * vive en la cookie HttpOnly del backend. Muestra el indicador de conexion
 * (Req 2.9, 18.5). Usa OnPush para minimizar el trabajo de deteccion de
 * cambios (Req 2).
 */
@Component({
  selector: 'cima-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    ConnectionStatusComponent,
    UserMenuComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a class="saltar" href="#contenido">Saltar al contenido</a>
    <header class="barra">
      <div class="barra__fila">
        <a routerLink="/inicio" class="barra__marca" aria-label="CIMA, ir al inicio">
          <img
            src="logos/sb-logo-horizontal-white.svg"
            alt="Seguros Bolívar"
            width="150"
            height="40"
          />
          <span class="barra__producto">CIMA</span>
        </a>
        @if (auth.autenticado()) {
          @if (resumen(); as r) {
            <ul class="chips" aria-label="Tu avance">
              <li class="chip" title="Días seguidos aprendiendo">
                <span aria-hidden="true">🔥</span> {{ r.streak_days }}
                <span class="solo-lector">días seguidos</span>
              </li>
              <li class="chip" title="Tus puntos">
                <span aria-hidden="true">★</span> {{ r.total_points }}
                <span class="solo-lector">puntos</span>
              </li>
              <li class="chip chip--nivel" title="Tu nivel">{{ r.level.name }}</li>
            </ul>
          }
          <cima-user-menu />
        }
      </div>
      @if (auth.autenticado()) {
        <nav class="nav" aria-label="Principal">
          <a routerLink="/inicio" routerLinkActive="activo">Inicio</a>
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
        z-index: 30;
        background: var(--cima-dorado);
        color: var(--cima-texto);
        padding: 0.5rem 1rem;
      }
      /* position: relative ancla el panel del menu de la cuenta. */
      .barra {
        position: relative;
        background: var(--cima-verde-oscuro);
        color: #fff;
      }
      .barra__fila {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.75rem 1rem;
        padding: 0.75rem 1rem;
      }
      /*
       * En celular: fila 1 = marca + "Mi cuenta", fila 2 = chips a todo el ancho.
       * Desde 640 px todo cabe en una sola fila (marca, chips, cuenta).
       */
      .barra__marca {
        order: 1;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-inline-end: auto;
        color: #fff;
        text-decoration: none;
      }
      cima-user-menu {
        order: 2;
      }
      .barra__marca img {
        height: 32px;
        width: auto;
      }
      .barra__producto {
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: var(--cima-dorado);
      }
      .chips {
        order: 3;
        flex-basis: 100%;
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        list-style: none;
        margin: 0;
        padding: 0;
      }
      @media (min-width: 640px) {
        .chips {
          order: 2;
          flex-basis: auto;
        }
        cima-user-menu {
          order: 3;
        }
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
      /* Barra desplazable: cada enlace conserva su ancho y no se encima con el vecino. */
      .nav {
        display: flex;
        gap: 0.25rem;
        overflow-x: auto;
        overscroll-behavior-x: contain;
        scrollbar-width: none;
        padding: 0 0.75rem;
        background: rgba(0, 0, 0, 0.18);
      }
      .nav::-webkit-scrollbar {
        display: none;
      }
      .nav a {
        flex: none;
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
      /*
       * Celulares angostos: marca mas compacta para que "Mi cuenta" quepa en la
       * primera fila. Va al final para ganar a las reglas base de igual
       * especificidad.
       */
      @media (max-width: 420px) {
        .barra__fila {
          padding-inline: 0.75rem;
          gap: 0.6rem 0.5rem;
        }
        .barra__marca {
          gap: 0.5rem;
        }
        .barra__marca img {
          height: 26px;
        }
        .barra__producto {
          font-size: 1.1rem;
        }
      }
    `,
  ],
})
export class AppComponent {
  protected readonly auth = inject(AuthService);
  private readonly gamificacion = inject(GamificationService);

  protected readonly resumen = this.gamificacion.resumen;

  constructor() {
    // Si la cookie de sesion sigue vigente, la app lo sabe sin pedir la Clave.
    void this.auth.restaurarSesion();
    // Con sesion se cargan los chips; al salir se limpian para no mostrar datos ajenos.
    effect(() => {
      if (this.auth.autenticado()) {
        void this.cargarChips();
      } else {
        this.gamificacion.limpiar();
      }
    });
  }

  /** Carga el resumen del encabezado; sin resumen no se muestran chips. */
  private async cargarChips(): Promise<void> {
    try {
      await this.gamificacion.cargarResumen();
    } catch {
      // Las vistas manejan su propio error; el encabezado simplemente no muestra chips.
    }
  }
}
