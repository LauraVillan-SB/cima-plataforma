import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { UserContextService } from '../core/user-context.service';

/**
 * Menú de la cuenta, visible en el encabezado de toda pantalla con sesión.
 * Dice quién es la persona (su cultivo o comercio y su celular enmascarado) y
 * da acceso a Inicio, sus microcápsulas, su perfil, el cambio de clave y el
 * cierre de sesión (Req 1.14, 9.1, 13.1).
 *
 * Accesibilidad (Req 13.2, 13.3): botón de despliegue con `aria-expanded` y
 * `aria-controls`; se cierra con Escape (devolviendo el foco al botón) y al
 * hacer clic fuera; cada opción mide al menos 56 px de alto. Solo
 * presentación: el celular llega del backend ya enmascarado (Req 9.4) y la
 * sesión vive en la cookie HttpOnly.
 */
@Component({
  selector: 'cima-user-menu',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:keydown.escape)': 'alPresionarEscape()',
    '(document:click)': 'alHacerClicEnDocumento($event)',
  },
  template: `
    <button
      #boton
      type="button"
      class="boton"
      aria-controls="menu-cuenta"
      [attr.aria-expanded]="abierto()"
      (click)="alternar()"
    >
      Mi cuenta
    </button>

    @if (abierto()) {
      <nav id="menu-cuenta" class="panel" aria-label="Opciones de tu cuenta">
        <div class="quien">
          <p class="quien__titulo">Tu cuenta</p>
          @if (contexto.cargando()) {
            <p class="quien__dato" role="status">Cargando tus datos...</p>
          } @else if (contexto.perfil(); as perfil) {
            <p class="quien__dato">
              Cultivo o comercio: <strong>{{ contexto.actividadEtiqueta() }}</strong>
            </p>
            <p class="quien__dato">
              Celular: <strong>{{ perfil.phone }}</strong>
            </p>
          } @else {
            <p class="quien__dato">Todavía no has completado tu perfil.</p>
          }
        </div>

        <ul class="lista">
          <li>
            <a class="opcion" routerLink="/inicio" routerLinkActive="activa"
               ariaCurrentWhenActive="page" (click)="cerrar()">Inicio</a>
          </li>
          <li>
            <a class="opcion" routerLink="/aprendizaje" routerLinkActive="activa"
               ariaCurrentWhenActive="page" (click)="cerrar()">Mis microcápsulas</a>
          </li>
          <li>
            <a class="opcion" routerLink="/perfil" routerLinkActive="activa"
               ariaCurrentWhenActive="page" (click)="cerrar()">Mi perfil</a>
          </li>
          <li>
            <a class="opcion" routerLink="/clave" routerLinkActive="activa"
               ariaCurrentWhenActive="page" (click)="cerrar()">Cambiar mi clave</a>
          </li>
          <li>
            <button
              type="button"
              class="opcion opcion--salir"
              [disabled]="saliendo()"
              (click)="salir()"
            >
              {{ saliendo() ? 'Saliendo...' : 'Cerrar sesión' }}
            </button>
          </li>
        </ul>

        @if (errorAlSalir()) {
          <p class="error" role="alert">
            No pudimos cerrar tu sesión. Revisa tu conexión e intenta de nuevo.
          </p>
        }
      </nav>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .boton {
        min-height: 48px;
        padding: 0 1.25rem;
        border: 0;
        border-radius: 8px;
        background: #fff;
        color: var(--cima-verde, #0a7d3c);
        font: inherit;
        font-size: 1.05rem;
        font-weight: 700;
        cursor: pointer;
      }
      /* Panel anclado al encabezado (que es position: relative). */
      .panel {
        position: absolute;
        top: 100%;
        right: 0;
        z-index: 20;
        width: min(24rem, 100%);
        max-height: calc(100svh - 4rem);
        overflow-y: auto;
        background: #fff;
        color: var(--cima-texto, #1a1a1a);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
      }
      .quien {
        padding: 1rem 1.25rem;
        background: #f5f5f5;
        border-bottom: 1px solid #d9d9d9;
      }
      .quien__titulo {
        margin: 0 0 0.25rem;
        font-size: 1.25rem;
        font-weight: 700;
      }
      .quien__dato {
        margin: 0.25rem 0 0;
        font-size: 1.05rem;
      }
      .lista {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .opcion {
        display: flex;
        align-items: center;
        width: 100%;
        min-height: 56px;
        padding: 0 1.25rem;
        border: 0;
        border-bottom: 1px solid #e3e3e3;
        border-left: 4px solid transparent;
        background: transparent;
        color: var(--cima-texto, #1a1a1a);
        font: inherit;
        font-size: 1.125rem;
        text-align: left;
        text-decoration: none;
        cursor: pointer;
      }
      .opcion.activa {
        border-left-color: var(--cima-verde, #0a7d3c);
        font-weight: 700;
      }
      .opcion--salir {
        color: #b00020;
        font-weight: 700;
      }
      .opcion:disabled {
        cursor: not-allowed;
        opacity: 0.7;
      }
      .error {
        margin: 0;
        padding: 0.75rem 1.25rem 1rem;
        color: #b00020;
        font-size: 1rem;
      }
    `,
  ],
})
export class UserMenuComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly anfitrion = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly boton = viewChild.required<ElementRef<HTMLButtonElement>>('boton');

  protected readonly contexto = inject(UserContextService);

  protected readonly abierto = signal<boolean>(false);
  protected readonly saliendo = signal<boolean>(false);
  protected readonly errorAlSalir = signal<boolean>(false);

  protected alternar(): void {
    this.abierto.update((v) => !v);
    this.errorAlSalir.set(false);
  }

  protected cerrar(): void {
    this.abierto.set(false);
  }

  /** Escape cierra el menú y devuelve el foco al botón que lo abrió. */
  protected alPresionarEscape(): void {
    if (this.abierto()) {
      this.cerrar();
      this.boton().nativeElement.focus();
    }
  }

  /** Un clic fuera del menú lo cierra. */
  protected alHacerClicEnDocumento(evento: Event): void {
    if (!this.abierto()) {
      return;
    }
    const objetivo = evento.target;
    if (objetivo instanceof Node && !this.anfitrion.nativeElement.contains(objetivo)) {
      this.cerrar();
    }
  }

  /**
   * Cierra la sesión en el backend y, solo si salió bien, lleva a la pantalla
   * de entrada. Si falla, se queda y avisa: no se muestra "entrar" mientras la
   * sesión sigue abierta.
   */
  protected async salir(): Promise<void> {
    this.saliendo.set(true);
    this.errorAlSalir.set(false);
    try {
      await this.auth.salir();
      this.cerrar();
      await this.router.navigate(['/entrar']);
    } catch {
      // Mensaje genérico; el detalle lo registra el backend.
      this.errorAlSalir.set(true);
    } finally {
      this.saliendo.set(false);
    }
  }
}
