import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { OfflineQueueService } from '../core/offline-queue.service';

/**
 * Indicador de estado de conexion y sincronizacion, en lenguaje simple y
 * accesible (Req 2.9, 18.5). Muestra un mensaje claro en espanol coloquial
 * segun haya o no conexion y acciones pendientes. Solo presentacion.
 */
@Component({
  selector: 'cima-connection-status',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- La region viva existe siempre para que el lector de pantalla anuncie
         los cambios; el texto solo aparece cuando hay algo que avisar. -->
    <div role="status" aria-live="polite">
      @if (hayAviso()) {
        <div
          class="sb-ui-alert estado"
          [class.sb-ui-alert--error]="esSinConexion()"
          [class.sb-ui-alert--info]="!esSinConexion()"
        >
          {{ mensaje() }}
        </div>
      }
    </div>
  `,
  styles: [
    `
      .estado {
        margin: 0.75rem 1rem 0;
      }
    `,
  ],
})
export class ConnectionStatusComponent {
  private readonly cola = inject(OfflineQueueService);

  readonly esSinConexion = computed(() => this.cola.estado() === 'sin_conexion');

  /** Solo se avisa cuando hay algo relevante; "al dia" no muestra nada. */
  readonly hayAviso = computed(() => this.cola.estado() !== 'al_dia');

  /** Traduce el estado tecnico a un mensaje simple para el Usuario. */
  readonly mensaje = computed<string>(() => {
    const pendientes = this.cola.pendientes();
    switch (this.cola.estado()) {
      case 'sin_conexion':
        return pendientes > 0
          ? `Sin conexion. Guardamos tus avances y los subimos cuando vuelva el internet.`
          : `Sin conexion. Puedes seguir, guardamos todo en tu telefono.`;
      case 'sincronizando':
        return `Subiendo tus avances...`;
      case 'pendiente':
        return `Tienes ${pendientes} avance(s) por subir.`;
      case 'al_dia':
      default:
        return `Todo al dia.`;
    }
  });
}
