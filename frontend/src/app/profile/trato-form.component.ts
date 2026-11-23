import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { UserContextService } from '../core/user-context.service';
import { MAX_NOMBRE, TRATOS, comoLlamar, crearPreferencia, type Trato } from '../core/trato';

/**
 * "¿Cómo quiere que le digamos?" (Req 13.1). La persona escoge "Doña", "Don" o
 * "Solo mi nombre" y escribe su nombre para que la app la salude ("Hola, doña
 * Rosa"). Es opcional y se guarda solo en este celular: no se envía al backend
 * ni al asistente (ver `core/trato.ts`). Controles grandes (Req 13.2, 13.3).
 */
@Component({
  selector: 'cima-trato-form',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form (ngSubmit)="guardar()" novalidate aria-labelledby="titulo-trato">
      <h2 class="titulo" id="titulo-trato">¿Cómo quiere que le digamos?</h2>
      <p class="ayuda">
        Es opcional. Su nombre se guarda solo en este celular: no lo enviamos a CIMA ni al
        asistente. Si cierra la sesión, se borra.
      </p>

      <fieldset class="opciones">
        <legend class="sb-ui-input-label">Quiero que me digan</legend>
        @for (opcion of tratos; track opcion.valor) {
          <label class="opcion">
            <input
              type="radio"
              name="trato"
              [value]="opcion.valor"
              [ngModel]="trato()"
              (ngModelChange)="trato.set($event)"
            />
            {{ opcion.etiqueta }}
          </label>
        }
      </fieldset>

      <div class="sb-ui-input-container campo">
        <label class="sb-ui-input-label" for="nombre-trato">Su nombre</label>
        <input
          id="nombre-trato"
          name="nombre"
          type="text"
          autocomplete="given-name"
          [attr.maxlength]="maxNombre"
          class="sb-ui-input sb-ui-input--large"
          [ngModel]="nombre()"
          (ngModelChange)="nombre.set($event)"
          placeholder="Ej: Rosa"
          aria-describedby="ayuda-nombre-trato"
        />
        <span id="ayuda-nombre-trato" class="sb-ui-input-helper">
          Solo letras, sin números. Puede ser solo el primer nombre.
        </span>
      </div>

      @if (vistaPrevia(); as como) {
        <p class="vista" aria-live="polite">Le saludaremos así: Hola, {{ como }}</p>
      }

      <button
        type="submit"
        class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large boton"
        [disabled]="!preferencia()"
      >
        Guardar en este celular
      </button>
      @if (contexto.trato()) {
        <button
          type="button"
          class="sb-ui-button sb-ui-button--primary sb-ui-button--text sb-ui-button--large boton"
          (click)="borrar()"
        >
          Borrar mi nombre de este celular
        </button>
      }

      @if (mensaje()) {
        <div class="sb-ui-alert sb-ui-alert--success aviso" role="status">{{ mensaje() }}</div>
      }
    </form>
  `,
  styles: [
    `
      .titulo {
        margin: 0 0 0.5rem;
        font-size: 1.35rem;
      }
      .ayuda {
        margin: 0 0 1rem;
      }
      .opciones {
        border: 0;
        margin: 0 0 1rem;
        padding: 0;
      }
      .opcion {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-height: 44px;
        font-size: 1.125rem;
        cursor: pointer;
      }
      .opcion input {
        width: 24px;
        height: 24px;
        margin: 0;
      }
      .campo {
        margin-bottom: 1rem;
      }
      .vista {
        margin: 0 0 1rem;
        font-weight: 700;
      }
      .boton {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin-top: 0.5rem;
      }
      .aviso {
        margin-top: 1rem;
      }
    `,
  ],
})
export class TratoFormComponent {
  protected readonly contexto = inject(UserContextService);

  protected readonly tratos = TRATOS;
  protected readonly maxNombre = MAX_NOMBRE;

  protected readonly trato = signal<Trato | ''>(this.contexto.trato()?.trato ?? '');
  protected readonly nombre = signal<string>(this.contexto.trato()?.nombre ?? '');
  protected readonly mensaje = signal<string>('');

  /** Preferencia válida con lo escrito, o `null` si falta algo o el nombre no es válido. */
  protected readonly preferencia = computed(() => crearPreferencia(this.trato(), this.nombre()));

  /** Cómo quedaría el saludo con lo escrito ("doña Rosa"). */
  protected readonly vistaPrevia = computed(() => comoLlamar(this.preferencia()));

  protected guardar(): void {
    const p = this.preferencia();
    if (!p) {
      return;
    }
    this.nombre.set(p.nombre);
    this.mensaje.set(
      this.contexto.guardarTrato(p)
        ? 'Listo, lo guardamos en este celular.'
        : 'Lo usaremos mientras tenga la app abierta; este celular no nos dejó guardarlo.',
    );
  }

  protected borrar(): void {
    this.contexto.borrarTrato();
    this.trato.set('');
    this.nombre.set('');
    this.mensaje.set('Listo, borramos su nombre de este celular.');
  }
}
