import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../auth/auth.service';

/**
 * Pantalla de inicio tras entrar (destino del login/registro). Es un marcador
 * de posicion: confirma que la sesion esta iniciada y permite salir. Las vistas
 * de dominio (aprendizaje, perfil, conversacion) se agregaran aqui a medida que
 * sus servicios esten disponibles. Solo presentacion; la sesion vive en la
 * cookie HttpOnly del backend (Req 2.6).
 */
@Component({
  selector: 'cima-home-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="inicio">
      <div class="sb-ui-card tarjeta">
        <div class="sb-ui-card__body">
          <h1 class="titulo">¡Entraste a CIMA!</h1>
          <p class="texto">
            Tu sesión está iniciada. Empieza por tus microcápsulas de
            aprendizaje; pronto sumaremos tu asistente y más.
          </p>
          <button
            type="button"
            class="sb-ui-button sb-ui-button--primary sb-ui-button--fill accion"
            (click)="irAAprendizaje()"
          >
            Ver mis microcápsulas
          </button>
          <button
            type="button"
            class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill salir"
            [disabled]="saliendo()"
            (click)="salir()"
          >
            {{ saliendo() ? 'Saliendo...' : 'Cerrar sesión' }}
          </button>
        </div>
      </div>
    </section>
  `,
  styles: [
    `
      .inicio {
        display: flex;
        justify-content: center;
        padding: 2.5rem 1rem;
      }
      .tarjeta {
        width: 100%;
        max-width: 420px;
        padding: 2rem 1.5rem;
        background: #fff;
        text-align: center;
      }
      .titulo {
        margin: 0 0 1rem;
        font-size: 1.25rem;
      }
      .texto {
        margin: 0 0 1.5rem;
        line-height: 1.5;
      }
      .accion {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin-bottom: 0.75rem;
      }
      .salir {
        display: block;
        width: 100%;
        box-sizing: border-box;
      }
    `,
  ],
})
export class HomePageComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly saliendo = signal<boolean>(false);

  async irAAprendizaje(): Promise<void> {
    await this.router.navigate(['/aprendizaje']);
  }

  async salir(): Promise<void> {
    this.saliendo.set(true);
    try {
      await this.auth.salir();
    } finally {
      this.saliendo.set(false);
      await this.router.navigate(['/entrar']);
    }
  }
}
