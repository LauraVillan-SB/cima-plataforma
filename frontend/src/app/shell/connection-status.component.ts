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
    <div
      class="estado"
      [class.estado--offline]="esSinConexion()"
      role="status"
      aria-live="polite"
    >
      {{ mensaje() }}
    </div>
  `,
  styles: [
    `
      .estado {
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 0.95rem;
        background: #e7f6ec;
        color: #0a5a2c;
      }
      .estado--offline {
        background: #fdecec;
        color: #8a1f1f;
      }
    `,
  ],
})
export class ConnectionStatusComponent {
  private readonly cola = inject(OfflineQueueService);

  readonly esSinConexion = computed(() => this.cola.estado() === 'sin_conexion');

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
