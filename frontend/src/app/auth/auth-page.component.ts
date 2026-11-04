import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { AuthService } from './auth.service';
import { esClaveValida, normalizarTelefono, CLAVE_LONGITUD } from './clave';

/** Mensaje generico: el backend no revela si el telefono existe (Req 1.8). */
const MENSAJE_GENERICO = 'No pudimos entrar. Revisa tu celular y tu clave e intenta de nuevo.';
const MENSAJE_BLOQUEO = 'Tu cuenta está bloqueada por seguridad. Intenta de nuevo en unos minutos.';

/**
 * Pantalla de autenticación sin fricción (Tarea 23.1).
 *
 * Solo teléfono + Clave de 4 dígitos, mensajes en español coloquial, sin correo
 * ni descargas (Req 1.1, 1.8). En el registro muestra un texto de ayuda que
 * sugiere usar los últimos 4 dígitos de la cédula como pista para recordar la
 * Clave, sin validarla contra la cédula ni almacenarla (solo texto de UI,
 * Req 1.3). Controles accesibles ≥ 44×44 px (Req 13.3). Solo presentación: la
 * autorización es del backend.
 *
 * Estilos: clases del Design System de Seguros Bolívar (`sb-ui-*`, bundle
 * @seguros-bolivar/ui-bundle). El layout propio (centrado) vive en `styles`.
 */
@Component({
  selector: 'cima-auth-page',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="pantalla">
      <div class="sb-ui-card sb-ui-card--outlined tarjeta">
        <div class="sb-ui-card__body">
          <header class="cabecera">
            <img
              class="logo"
              src="logos/sb-logo-horizontal.svg"
              alt="Seguros Bolívar"
              width="180"
              height="48"
            />
            <p class="subtitulo">Escuela de Sostenibilidad e Inclusión</p>
          </header>

          <h1 class="titulo" id="titulo-auth">
            {{ modoRegistro() ? 'Crea tu cuenta' : 'Entra a CIMA' }}
          </h1>

          <form (ngSubmit)="enviar()" novalidate aria-labelledby="titulo-auth">
            <div class="sb-ui-input-container campo">
              <label class="sb-ui-input-label" for="telefono">Tu celular</label>
              <input
                id="telefono"
                name="telefono"
                type="tel"
                inputmode="numeric"
                autocomplete="tel"
                class="sb-ui-input"
                [(ngModel)]="telefono"
                placeholder="Ej: 3001234567"
                aria-describedby="ayuda-telefono"
              />
              <span id="ayuda-telefono" class="sb-ui-input-helper">Escribe tu número de celular.</span>
            </div>

            <div class="sb-ui-input-container campo">
              <label class="sb-ui-input-label" for="clave">Tu clave de {{ longitudClave }} números</label>
              <input
                id="clave"
                name="clave"
                type="password"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="4"
                class="sb-ui-input"
                [(ngModel)]="clave"
                aria-describedby="ayuda-clave"
              />
              @if (modoRegistro()) {
                <span id="ayuda-clave" class="sb-ui-input-helper">
                  Para acordarte fácil, puedes usar los últimos 4 números de tu cédula.
                </span>
              } @else {
                <span id="ayuda-clave" class="sb-ui-input-helper">Escribe tu clave de 4 números.</span>
              }
            </div>

            <button
              type="submit"
              class="sb-ui-button sb-ui-button--primary sb-ui-button--fill enviar"
              [disabled]="!formularioValido() || cargando()"
            >
              {{ cargando() ? 'Un momento...' : modoRegistro() ? 'Crear cuenta' : 'Entrar' }}
            </button>
          </form>

          @if (mensaje()) {
            <div class="sb-ui-alert sb-ui-alert--error aviso" role="alert">
              {{ mensaje() }}
            </div>
          }

          <div class="cambiar-modo">
            <button
              type="button"
              class="sb-ui-button sb-ui-button--primary sb-ui-button--text"
              (click)="alternarModo()"
            >
              {{ modoRegistro() ? 'Ya tengo cuenta, quiero entrar' : 'Soy nuevo, quiero crear mi cuenta' }}
            </button>
          </div>
        </div>
      </div>
    </main>
  `,
  styles: [
    `
      .pantalla {
        display: flex;
        justify-content: center;
        padding: 2.5rem 1rem;
      }
      .tarjeta {
        width: 100%;
        max-width: 420px;
        padding: 2rem 1.5rem;
        background: #fff;
        overflow: hidden;
      }
      .enviar {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin-top: 0.5rem;
      }
      .cabecera {
        text-align: center;
        margin-bottom: 1.5rem;
      }
      .logo {
        max-width: 100%;
        height: auto;
      }
      .subtitulo {
        margin: 0.5rem 0 0;
        font-size: 0.85rem;
      }
      .titulo {
        margin: 0 0 1.5rem;
        text-align: center;
        font-size: 1.25rem;
      }
      .campo {
        margin-bottom: 1rem;
      }
      .aviso {
        margin-top: 1rem;
      }
      .cambiar-modo {
        text-align: center;
        margin-top: 1.25rem;
      }
    `,
  ],
})
export class AuthPageComponent {
  private readonly auth = inject(AuthService);

  readonly longitudClave = CLAVE_LONGITUD;
  readonly modoRegistro = signal<boolean>(false);
  readonly telefono = signal<string>('');
  readonly clave = signal<string>('');
  readonly cargando = signal<boolean>(false);
  readonly mensaje = signal<string>('');

  readonly formularioValido = computed(
    () => normalizarTelefono(this.telefono()).replace('+', '').length >= 7 && esClaveValida(this.clave()),
  );

  alternarModo(): void {
    this.modoRegistro.update((v) => !v);
    this.mensaje.set('');
  }

  async enviar(): Promise<void> {
    if (!this.formularioValido()) {
      return;
    }
    this.cargando.set(true);
    this.mensaje.set('');
    const tel = normalizarTelefono(this.telefono());
    try {
      if (this.modoRegistro()) {
        await this.auth.registrar(tel, this.clave());
      } else {
        await this.auth.ingresar(tel, this.clave());
      }
    } catch (error: unknown) {
      this.mensaje.set(this.mensajeDeError(error));
    } finally {
      this.cargando.set(false);
    }
  }

  /**
   * Traduce el error del backend a un mensaje para el Usuario. Solo el bloqueo
   * (HTTP 429) usa el texto del servidor, que indica los minutos de espera; el
   * resto conserva el mensaje generico para no revelar si el telefono existe.
   */
  private mensajeDeError(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 429) {
      const detalle: unknown = error.error?.detail;
      return typeof detalle === 'string' && detalle.trim() ? detalle : MENSAJE_BLOQUEO;
    }
    return MENSAJE_GENERICO;
  }
}
