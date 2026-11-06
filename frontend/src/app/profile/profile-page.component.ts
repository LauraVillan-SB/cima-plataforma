import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { UserContextService } from '../core/user-context.service';
import { ProfileService, type Perfil } from './profile.service';
import { TIPOS_ACTIVIDAD, esActividadValida, esZonaValida } from './perfil';

/**
 * Pantalla de Perfil del Usuario (Tarea 23, Req 9.1, 9.4, 9.5). Muestra y edita
 * el Perfil propio contra el Profile Service. El teléfono se muestra enmascarado
 * tal como lo envía el backend (solo lectura); el Usuario edita el tipo de
 * cultivo o comercio y la zona. Solo presentación: la validación y la
 * autorización por propiedad del recurso (anti-BOLA) son del backend.
 *
 * Al cargar o guardar el Perfil se comparte con el contexto de la sesión para
 * que el saludo del inicio y el menú de la cuenta se actualicen al instante.
 * Campos y botones grandes (variantes `--large` del Design System, Req 13.2, 13.3).
 */
@Component({
  selector: 'cima-profile-page',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pantalla">
      <div class="sb-ui-card tarjeta">
        <div class="sb-ui-card__body">
          <h1 class="titulo" id="titulo-perfil">
            {{ perfilExiste() ? 'Tu perfil' : 'Completa tu perfil' }}
          </h1>

          @if (cargandoInicial()) {
            <p class="texto" role="status">Cargando tu perfil...</p>
          } @else {
            <form (ngSubmit)="guardar()" novalidate aria-labelledby="titulo-perfil">
              @if (perfilExiste()) {
                <div class="sb-ui-input-container campo">
                  <span class="sb-ui-input-label">Tu celular</span>
                  <p class="dato" aria-live="polite">{{ telefonoEnmascarado() }}</p>
                  <span class="sb-ui-input-helper">
                    Por tu seguridad solo mostramos los últimos números.
                  </span>
                </div>
              }

              <div class="sb-ui-input-container campo">
                <label class="sb-ui-input-label" for="actividad">Tu cultivo o comercio</label>
                <select
                  id="actividad"
                  name="actividad"
                  class="sb-ui-input sb-ui-input--large"
                  [ngModel]="actividad()"
                  (ngModelChange)="actividad.set($event)"
                  aria-describedby="ayuda-actividad"
                >
                  <option value="" disabled>Elige una opción</option>
                  @for (opcion of tiposActividad; track opcion.valor) {
                    <option [value]="opcion.valor">{{ opcion.etiqueta }}</option>
                  }
                </select>
                <span id="ayuda-actividad" class="sb-ui-input-helper">
                  Escoge a qué te dedicas.
                </span>
              </div>

              <div class="sb-ui-input-container campo">
                <label class="sb-ui-input-label" for="zona">Tu zona</label>
                <input
                  id="zona"
                  name="zona"
                  type="text"
                  maxlength="100"
                  class="sb-ui-input sb-ui-input--large"
                  [ngModel]="zona()"
                  (ngModelChange)="zona.set($event)"
                  placeholder="Ej: Vereda El Carmen, Huila"
                  aria-describedby="ayuda-zona"
                />
                <span id="ayuda-zona" class="sb-ui-input-helper">
                  Escribe el nombre de tu vereda, municipio o barrio.
                </span>
              </div>

              <button
                type="submit"
                class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large guardar"
                [disabled]="!formularioValido() || guardando()"
              >
                {{ guardando() ? 'Guardando...' : 'Guardar' }}
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
      .texto {
        text-align: center;
        font-size: 1.125rem;
      }
      .campo {
        margin-bottom: 1.25rem;
      }
      .dato {
        margin: 0.25rem 0;
        font-weight: 700;
        font-size: 1.25rem;
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
export class ProfilePageComponent {
  private readonly profiles = inject(ProfileService);
  private readonly router = inject(Router);
  private readonly contexto = inject(UserContextService);

  readonly tiposActividad = TIPOS_ACTIVIDAD;

  private readonly perfil = signal<Perfil | null>(null);
  readonly cargandoInicial = signal<boolean>(true);
  readonly guardando = signal<boolean>(false);
  readonly mensajeOk = signal<string>('');
  readonly mensajeError = signal<string>('');

  readonly actividad = signal<string>('');
  readonly zona = signal<string>('');

  readonly perfilExiste = computed(() => this.perfil() !== null);
  readonly telefonoEnmascarado = computed(() => this.perfil()?.phone ?? '');

  readonly formularioValido = computed(
    () => esActividadValida(this.actividad()) && esZonaValida(this.zona()),
  );

  constructor() {
    void this.cargar();
  }

  /** Carga el Perfil propio; si aún no existe (404), deja el formulario vacío. */
  private async cargar(): Promise<void> {
    try {
      const perfil = await this.profiles.obtenerMiPerfil();
      this.perfil.set(perfil);
      this.contexto.establecer(perfil);
      this.actividad.set(perfil.activity_type);
      this.zona.set(perfil.geo_zone);
    } catch (error: unknown) {
      if (error instanceof HttpErrorResponse && error.status === 404) {
        this.perfil.set(null);
      } else {
        this.mensajeError.set('No pudimos cargar tu perfil. Intenta de nuevo.');
      }
    } finally {
      this.cargandoInicial.set(false);
    }
  }

  async guardar(): Promise<void> {
    if (!this.formularioValido()) {
      return;
    }
    this.guardando.set(true);
    this.mensajeOk.set('');
    this.mensajeError.set('');
    const actual = this.perfil();
    const activity_type = this.actividad();
    const geo_zone = this.zona().trim();
    try {
      // Al actualizar solo se envían cultivo/comercio y zona: el celular es la
      // identidad de ingreso, no se edita aquí y el cliente solo lo ve enmascarado.
      const guardado = actual
        ? await this.profiles.actualizar(actual.id, { activity_type, geo_zone })
        : await this.profiles.crear({ phone: '', activity_type, geo_zone });
      this.perfil.set(guardado);
      this.contexto.establecer(guardado);
      this.actividad.set(guardado.activity_type);
      this.zona.set(guardado.geo_zone);
      this.mensajeOk.set('Guardamos tus cambios.');
    } catch (error: unknown) {
      this.mensajeError.set(this.mensajeDeError(error));
    } finally {
      this.guardando.set(false);
    }
  }

  async volver(): Promise<void> {
    await this.router.navigate(['/inicio']);
  }

  /** Traduce el error del backend a un mensaje para el Usuario, sin filtrar detalles. */
  private mensajeDeError(error: unknown): string {
    if (error instanceof HttpErrorResponse && error.status === 422) {
      return 'Revisa los datos: el cultivo/comercio y la zona son obligatorios.';
    }
    return 'No pudimos guardar tus cambios. Intenta de nuevo.';
  }
}
