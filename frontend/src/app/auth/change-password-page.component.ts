import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from './auth.service';
import { CLAVE_LONGITUD, esClaveValida } from './clave';

/**
 * Pantalla para cambiar la Clave de 4 números (Req 1.14). Pide la Clave actual,
 * la nueva y su confirmación. Solo presentación: la Clave actual la verifica el
 * backend, que además guarda la nueva solo como hash (Req 1.5). Las Claves
 * nunca se guardan en el navegador ni se escriben en ningún registro; los
 * campos se vacían apenas el cambio sale bien.
 *
 * Accesibilidad (Req 13.2, 13.3): campos y botones grandes (variantes
 * `--large` del Design System), etiquetas visibles, ayudas asociadas con
 * `aria-describedby` y avisos con `role="status"` / `role="alert"`.
 */
@Component({
  selector: 'cima-change-password-page',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pantalla">
      <div class="sb-ui-card tarjeta">
        <div class="sb-ui-card__body">
          <h1 class="titulo" id="titulo-clave">Cambiar mi clave</h1>

          <form (ngSubmit)="guardar()" novalidate aria-labelledby="titulo-clave">
            <div class="sb-ui-input-container campo">
              <label class="sb-ui-input-label" for="clave-actual">Tu clave de ahora</label>
              <input
                id="clave-actual"
                name="claveActual"
                type="password"
                inputmode="numeric"
                autocomplete="off"
                [maxlength]="longitudClave"
                class="sb-ui-input sb-ui-input--large"
                [ngModel]="claveActual()"
                (ngModelChange)="claveActual.set($event)"
                aria-describedby="ayuda-actual"
              />
              <span id="ayuda-actual" class="sb-ui-input-helper">
                Escribe los {{ longitudClave }} números que usas hoy para entrar.
              </span>
            </div>

            <div class="sb-ui-input-container campo">
              <label class="sb-ui-input-label" for="clave-nueva">Tu clave nueva</label>
              <input
                id="clave-nueva"
                name="claveNueva"
                type="password"
                inputmode="numeric"
                autocomplete="off"
                [maxlength]="longitudClave"
                class="sb-ui-input sb-ui-input--large"
                [ngModel]="claveNueva()"
                (ngModelChange)="claveNueva.set($event)"
                aria-describedby="ayuda-nueva"
              />
              <span id="ayuda-nueva" class="sb-ui-input-helper">
                Escoge {{ longitudClave }} números que puedas recordar fácil.
              </span>
            </div>

            <div class="sb-ui-input-container campo">
              <label class="sb-ui-input-label" for="clave-confirmacion">
                Escribe otra vez tu clave nueva
              </label>
              <input
                id="clave-confirmacion"
                name="confirmacion"
                type="password"
                inputmode="numeric"
                autocomplete="off"
                [maxlength]="longitudClave"
                class="sb-ui-input sb-ui-input--large"
                [ngModel]="confirmacion()"
                (ngModelChange)="confirmacion.set($event)"
                aria-describedby="ayuda-confirmacion"
              />
              <span id="ayuda-confirmacion" class="sb-ui-input-helper" aria-live="polite">
                @if (noCoinciden()) {
                  Las dos claves nuevas no son iguales. Revísalas.
                } @else {
                  Tiene que ser igual a la clave nueva.
                }
              </span>
            </div>

            <button
              type="submit"
              class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large guardar"
              [disabled]="!formularioValido() || guardando()"
            >
              {{ guardando() ? 'Guardando...' : 'Cambiar mi clave' }}
            </button>
          </form>

          @if (mensajeOk()) {
            <div class="sb-ui-alert sb-ui-alert--success aviso" role="status">
              {{ mensajeOk() }}
            </div>
          }
          @if (mensajeError()) {
            <div class="sb-ui-alert sb-ui-alert--error aviso" role="alert">
              {{ mensajeError() }}
            </div>
          }

          <div class="volver">
            <button
              type="button"
              class="sb-ui-button sb-ui-button--primary sb-ui-button--text sb-ui-button--large"
              (click)="volver()"
            >
              Volver al inicio
            </button>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [
    `
      .pantalla {
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
        margin: 0 0 1.5rem;
        text-align: center;
      }
      .campo {
        margin-bottom: 1.25rem;
      }
      .guardar {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin-top: 0.5rem;
      }
      .aviso {
        margin-top: 1rem;
      }
      .volver {
        text-align: center;
        margin-top: 1.25rem;
      }
    `,
  ],
})
export class ChangePasswordPageComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly longitudClave = CLAVE_LONGITUD;

  protected readonly claveActual = signal<string>('');
  protected readonly claveNueva = signal<string>('');
  protected readonly confirmacion = signal<string>('');

  protected readonly guardando = signal<boolean>(false);
  protected readonly mensajeOk = signal<string>('');
  protected readonly mensajeError = signal<string>('');

  /** Avisa que las dos claves nuevas difieren, solo cuando ya escribió la confirmación completa. */
  protected readonly noCoinciden = computed(
    () => esClaveValida(this.confirmacion()) && this.confirmacion() !== this.claveNueva(),
  );

  protected readonly formularioValido = computed(
    () =>
      esClaveValida(this.claveActual()) &&
      esClaveValida(this.claveNueva()) &&
      this.confirmacion() === this.claveNueva(),
  );

  protected async guardar(): Promise<void> {
    if (!this.formularioValido()) {
      return;
    }
    this.guardando.set(true);
    this.mensajeOk.set('');
    this.mensajeError.set('');
    try {
      await this.auth.cambiarClave(this.claveActual(), this.claveNueva(), this.confirmacion());
      this.claveActual.set('');
      this.claveNueva.set('');
      this.confirmacion.set('');
      this.mensajeOk.set('Listo, cambiamos tu clave. La próxima vez entra con la nueva.');
    } catch (error: unknown) {
      this.mensajeError.set(this.mensajeDeError(error));
    } finally {
      this.guardando.set(false);
    }
  }

  protected async volver(): Promise<void> {
    await this.router.navigate(['/inicio']);
  }

  /** Traduce el error del backend a un mensaje claro, sin revelar detalles internos. */
  private mensajeDeError(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) {
        return 'Tu clave de ahora no es correcta. Revísala e intenta de nuevo.';
      }
      if (error.status === 422) {
        return 'Revisa tus claves: deben ser de 4 números y la nueva debe escribirse igual dos veces.';
      }
    }
    return 'No pudimos cambiar tu clave. Intenta de nuevo en un momento.';
  }
}
