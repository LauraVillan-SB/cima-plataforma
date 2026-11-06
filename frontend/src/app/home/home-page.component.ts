import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { UserContextService } from '../core/user-context.service';

/**
 * Pantalla de inicio tras entrar (destino del login/registro). Saluda a la
 * persona nombrando su cultivo o comercio ("Hola, estas son tus opciones para
 * tu cultivo de café") y ofrece lo principal con botones grandes: sus
 * microcápsulas, su perfil, cambiar su clave y cerrar sesión (Req 13.1, 13.3).
 * Solo presentación; la sesión vive en la cookie HttpOnly del backend (Req 2.6)
 * y el Perfil llega con el celular ya enmascarado (Req 9.4).
 */
@Component({
  selector: 'cima-home-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="inicio">
      <div class="sb-ui-card tarjeta">
        <div class="sb-ui-card__body">
          <h1 class="titulo">
            @if (contexto.actividadFrase(); as frase) {
              Hola, estas son tus opciones para {{ frase }}
            } @else {
              Hola, estas son tus opciones
            }
          </h1>

          @if (contexto.cargando()) {
            <p class="texto" role="status">Un momento, estamos buscando tus datos...</p>
          } @else if (!contexto.perfil()) {
            <p class="texto">
              Cuéntanos a qué te dedicas en tu perfil y te mostramos lo que más te sirve.
            </p>
          }

          <button
            type="button"
            class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large accion"
            (click)="ir('/aprendizaje')"
          >
            Ver mis microcápsulas
          </button>
          <button
            type="button"
            class="sb-ui-button sb-ui-button--primary sb-ui-button--stroke sb-ui-button--large accion"
            (click)="ir('/perfil')"
          >
            {{ contexto.perfil() ? 'Ver mi perfil' : 'Completar mi perfil' }}
          </button>
          <button
            type="button"
            class="sb-ui-button sb-ui-button--primary sb-ui-button--stroke sb-ui-button--large accion"
            (click)="ir('/clave')"
          >
            Cambiar mi clave
          </button>
          <button
            type="button"
            class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large accion"
            [disabled]="saliendo()"
            (click)="salir()"
          >
            {{ saliendo() ? 'Saliendo...' : 'Cerrar sesión' }}
          </button>

          @if (errorAlSalir()) {
            <div class="sb-ui-alert sb-ui-alert--error aviso" role="alert">
              No pudimos cerrar tu sesión. Revisa tu conexión e intenta de nuevo.
            </div>
          }
        </div>
      </div>
    </section>
  `,
  styles: [
    `
      .inicio {
        display: flex;
        justify-content: center;
        padding: 2rem 1rem;
      }
      .tarjeta {
        width: 100%;
        max-width: 560px;
        padding: 2rem 1.5rem;
        background: #fff;
      }
      .titulo {
        margin: 0 0 1rem;
        text-align: center;
      }
      .texto {
        margin: 0 0 1.5rem;
        text-align: center;
        font-size: 1.125rem;
      }
      .accion {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin-bottom: 1rem;
      }
      .aviso {
        margin-top: 0.5rem;
      }
    `,
  ],
})
export class HomePageComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly contexto = inject(UserContextService);

  protected readonly saliendo = signal<boolean>(false);
  protected readonly errorAlSalir = signal<boolean>(false);

  protected async ir(ruta: string): Promise<void> {
    await this.router.navigate([ruta]);
  }

  /**
   * Cierra la sesión y, solo si salió bien, lleva a la pantalla de entrada. Si
   * falla se queda y avisa, para no mostrar "entrar" con la sesión aún abierta.
   */
  protected async salir(): Promise<void> {
    this.saliendo.set(true);
    this.errorAlSalir.set(false);
    try {
      await this.auth.salir();
      await this.router.navigate(['/entrar']);
    } catch {
      // Mensaje genérico; el detalle lo registra el backend.
      this.errorAlSalir.set(true);
    } finally {
      this.saliendo.set(false);
    }
  }
}
