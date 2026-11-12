import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { mensajeDeError } from '../core/mensaje-error';
import { OfflineQueueService } from '../core/offline-queue.service';
import {
  ConversionService,
  IntencionRegistrada,
  OfertaMicroseguros,
} from './conversion.service';

/**
 * Pantalla de opciones de microseguro tras terminar una ruta (Tarea 23.3,
 * Req 5). Presenta las opciones que el backend define para la actividad del
 * Usuario y registra su interés. CIMA no vende, no cobra ni emite pólizas: lo
 * dice la pantalla de forma explícita y el backend solo guarda la intención.
 * Si no hay opciones para su actividad se le informa (Req 5.8). El registro es
 * idempotente: ante un fallo se reintenta con el mismo `client_event_id` para
 * no duplicar (Req 5.6). Sin PII.
 */
@Component({
  selector: 'cima-conversion-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    <section class="conversion">
      <h1 class="titulo">Protege lo que has construido</h1>
      <p class="aviso">
        Esto no es una compra ni una póliza. Solo nos cuentas qué opción te interesa y así
        sabemos qué te sirve.
      </p>

      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Buscando opciones para ti...</p>
      } @else if (errorCarga(); as msg) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          {{ msg }}
          <button type="button" class="sb-ui-button sb-ui-button--secondary" (click)="cargar()">
            Reintentar
          </button>
        </div>
      } @else if (registrada()) {
        <div class="sb-ui-alert sb-ui-alert--success" role="status">
          <p>¡Listo! Registramos tu interés. Gracias por contarnos.</p>
        </div>
        <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large" routerLink="/inicio">
          Volver al inicio
        </a>
      } @else if (oferta(); as o) {
        @if (o.options.length === 0) {
          <div class="sb-ui-alert sb-ui-alert--info" role="status">
            Por ahora no tenemos opciones de microseguro para tu actividad. Seguiremos
            avisándote cuando haya novedades.
          </div>
        } @else {
          <form (ngSubmit)="registrar()">
            <fieldset class="opciones">
              <legend class="leyenda">¿Cuál te interesa?</legend>
              @for (op of o.options; track op.codigo) {
                <label class="opcion">
                  <input
                    type="radio"
                    name="opcion"
                    [value]="op.codigo"
                    [checked]="seleccion() === op.codigo"
                    (change)="elegir(op.codigo)"
                  />
                  <span>
                    <strong>{{ op.nombre }}</strong>
                    <span class="descripcion">{{ op.descripcion }}</span>
                  </span>
                </label>
              }
            </fieldset>

            @if (errorEnvio(); as msg) {
              <div class="sb-ui-alert sb-ui-alert--error" role="alert">{{ msg }}</div>
            }

            <button
              type="submit"
              class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large"
              [disabled]="enviando() || !seleccion()"
            >
              {{ enviando() ? 'Registrando...' : 'Me interesa' }}
            </button>
          </form>
        }
      }
    </section>
  `,
  styles: [
    `
      .conversion {
        padding: 1.5rem 1rem;
        max-width: 560px;
        margin: 0 auto;
      }
      .titulo {
        margin: 0 0 0.5rem;
      }
      .aviso,
      .estado {
        line-height: 1.5;
      }
      .opciones {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
      }
      .leyenda {
        font-weight: 600;
        padding: 0 0.25rem;
      }
      .opcion {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        min-height: 44px;
        padding: 0.5rem 0;
        line-height: 1.4;
      }
      .descripcion {
        display: block;
      }
    `,
  ],
})
export class ConversionPageComponent {
  private readonly conversion = inject(ConversionService);
  private readonly route = inject(ActivatedRoute);

  private readonly rutaId = this.route.snapshot.paramMap.get('rutaId') ?? '';

  /** Clave de idempotencia de la opción que se está registrando (Req 5.6). */
  private intento: { readonly codigo: string; readonly clientEventId: string } | null = null;

  readonly cargando = signal<boolean>(true);
  readonly errorCarga = signal<string | null>(null);
  readonly errorEnvio = signal<string | null>(null);
  readonly enviando = signal<boolean>(false);
  readonly oferta = signal<OfertaMicroseguros | null>(null);
  readonly seleccion = signal<string | null>(null);
  readonly registrada = signal<IntencionRegistrada | null>(null);

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.errorCarga.set(null);
    try {
      this.oferta.set(await this.conversion.obtenerOferta(this.rutaId));
    } catch (error) {
      this.errorCarga.set(
        mensajeDeError(error, 'No pudimos cargar las opciones. Revisa tu conexión e intenta de nuevo.'),
      );
    } finally {
      this.cargando.set(false);
    }
  }

  elegir(codigo: string): void {
    this.seleccion.set(codigo);
  }

  async registrar(): Promise<void> {
    const codigo = this.seleccion();
    if (!codigo || this.enviando()) {
      return;
    }
    // Misma opción => misma clave, así un reintento no duplica el registro.
    const intento =
      this.intento?.codigo === codigo
        ? this.intento
        : { codigo, clientEventId: OfflineQueueService.generarClaveIdempotencia() };
    this.intento = intento;

    this.enviando.set(true);
    this.errorEnvio.set(null);
    try {
      this.registrada.set(
        await this.conversion.registrarIntencion(this.rutaId, intento.clientEventId, codigo),
      );
    } catch (error) {
      this.errorEnvio.set(
        mensajeDeError(error, 'No pudimos registrar tu interés. Intenta de nuevo.'),
      );
    } finally {
      this.enviando.set(false);
    }
  }
}
