import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AuthService } from './auth.service';
import { esClaveValida, normalizarTelefono, CLAVE_LONGITUD } from './clave';

/**
 * Pantalla de autenticación sin fricción (Tarea 23.1).
 *
 * Solo teléfono + Clave de 4 dígitos, mensajes en español coloquial, sin correo
 * ni descargas (Req 1.1, 1.8). En el registro muestra un texto de ayuda que
 * sugiere usar los últimos 4 dígitos de la cédula como pista para recordar la
 * Clave, sin validarla contra la cédula ni almacenarla (solo texto de UI,
 * Req 1.3). Controles accesibles ≥ 44×44 px (Req 13.3). Solo presentación: la
 * autorización es del backend.
 */
@Component({
  selector: 'cima-auth-page',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="auth" aria-labelledby="titulo-auth">
      <h2 id="titulo-auth">{{ modoRegistro() ? 'Crea tu cuenta' : 'Entra a CIMA' }}</h2>

      <form (ngSubmit)="enviar()">
        <label for="telefono">Tu celular</label>
        <input
          id="telefono"
          name="telefono"
          type="tel"
          inputmode="numeric"
          autocomplete="tel"
          [(ngModel)]="telefono"
          placeholder="Ej: 3001234567"
          aria-describedby="ayuda-telefono"
        />
        <p id="ayuda-telefono" class="ayuda">Escribe tu numero de celular.</p>

        <label for="clave">Tu clave de {{ longitudClave }} numeros</label>
        <input
          id="clave"
          name="clave"
          type="password"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="4"
          [(ngModel)]="clave"
          aria-describedby="ayuda-clave"
        />
        @if (modoRegistro()) {
          <p id="ayuda-clave" class="ayuda">
            Para acordarte facil, puedes usar los ultimos 4 numeros de tu cedula.
          </p>
        } @else {
          <p id="ayuda-clave" class="ayuda">Escribe tu clave de 4 numeros.</p>
        }

        <button type="submit" [disabled]="!formularioValido() || cargando()">
          {{ cargando() ? 'Un momento...' : modoRegistro() ? 'Crear cuenta' : 'Entrar' }}
        </button>
      </form>

      @if (mensaje()) {
        <p class="mensaje" role="alert">{{ mensaje() }}</p>
      }

      <button type="button" class="enlace" (click)="alternarModo()">
        {{ modoRegistro() ? 'Ya tengo cuenta, quiero entrar' : 'Soy nuevo, quiero crear mi cuenta' }}
      </button>
    </section>
  `,
  styles: [
    `
      .auth {
        max-width: 420px;
        margin: 0 auto;
        padding: 16px;
      }
      label {
        display: block;
        margin-top: 12px;
        font-weight: 600;
      }
      input {
        width: 100%;
        min-height: 44px;
        font-size: 1rem;
        padding: 8px;
        border: 2px solid #0a7d3c;
        border-radius: 8px;
      }
      .ayuda {
        font-size: 0.9rem;
        color: #3a3a3a;
        margin: 4px 0 0;
      }
      button[type='submit'] {
        margin-top: 16px;
        width: 100%;
        min-height: 48px;
        font-size: 1rem;
        color: #fff;
        background: #0a7d3c;
        border: none;
        border-radius: 8px;
      }
      button[type='submit']:disabled {
        background: #9ec9af;
      }
      .enlace {
        margin-top: 16px;
        background: none;
        border: none;
        color: #0a5a2c;
        text-decoration: underline;
        min-height: 44px;
      }
      .mensaje {
        margin-top: 12px;
        color: #8a1f1f;
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
    } catch {
      // Mensaje generico coloquial; el backend no revela si el telefono existe.
      this.mensaje.set('No pudimos entrar. Revisa tu celular y tu clave e intenta de nuevo.');
    } finally {
      this.cargando.set(false);
    }
  }
}
