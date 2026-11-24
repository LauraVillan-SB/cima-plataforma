import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  AssessmentService,
  Evaluacion,
  ResultadoIntento,
} from './assessment.service';

/**
 * Pantalla de evaluación de una ruta (Tarea 23.3, Req 7). Presenta las preguntas
 * (sin la clave de respuestas, que vive en el servidor), captura la opción
 * elegida por pregunta y envía el intento. El puntaje, la aprobación, los
 * reintentos y el enfriamiento los calcula y controla el backend (Req 7.2–7.7);
 * aquí solo se recogen las selecciones y se muestra el resultado. Sin PII.
 *
 * Al terminar dice con claridad si la persona aprobó o si debe repasar, cuántas
 * preguntas acertó y qué puede hacer ahora. No indica cuáles preguntas falló:
 * eso permitiría deducir la clave de respuestas entre intentos (Req 7.6).
 */
@Component({
  selector: 'cima-assessment-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    <section class="evaluacion">
      <h1 class="titulo">Evaluación</h1>

      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Cargando la evaluación...</p>
      } @else if (errorCarga()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar la evaluación. Revise su conexión e intente de nuevo.
        </div>
      } @else if (resultado(); as r) {
        <section
          class="resultado"
          [class.resultado--ok]="r.passed"
          [class.resultado--repasar]="!r.passed"
          role="status"
          aria-live="polite"
        >
          <p class="resultado__icono" aria-hidden="true">{{ r.passed ? '🎉' : '📚' }}</p>
          <h2 class="resultado__titulo">
            {{ r.passed ? '¡Felicitaciones, aprobó!' : 'Le falta repasar un poco más' }}
          </h2>
          @if (totalPreguntas() > 0) {
            <p class="resultado__aciertos">
              Acertó {{ aciertos(r) }} de {{ totalPreguntas() }} preguntas.
            </p>
          }

          @if (r.passed) {
            <p class="resultado__texto">
              Terminó esta ruta con éxito. Ya puede ver su certificado.
            </p>
            <a
              class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large accion"
              [routerLink]="['/certificado', rutaId]"
            >
              Ver mi certificado
            </a>
            <a
              class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large accion"
              [routerLink]="['/conversion', rutaId]"
            >
              Ver opciones de microseguro
            </a>
          } @else {
            <p class="resultado__texto">
              Repase las lecciones de esta ruta y vuelva a intentarlo.
            </p>
            @if (r.cooldown_until) {
              <p class="resultado__texto">
                Usó todos sus intentos por ahora. Podrá volver a intentarlo
                {{ cuando(r.cooldown_until) }}.
              </p>
            } @else {
              <p class="resultado__texto">{{ textoIntentos(r.attempts_remaining) }}</p>
            }
            <a
              class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large accion"
              routerLink="/mi-ruta"
            >
              Repasar las lecciones
            </a>
            @if (!r.cooldown_until) {
              <button
                type="button"
                class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large accion"
                (click)="intentarDeNuevo()"
              >
                Intentar de nuevo
              </button>
            }
          }
        </section>
      } @else if (evaluacion(); as ev) {
        <form (submit)="alEnviar($event, ev)">
          @for (q of ev.questions; track q.id) {
            <fieldset class="pregunta">
              <legend class="enunciado">{{ q.prompt }}</legend>
              @for (opcion of q.options; track $index) {
                <label class="opcion">
                  <input
                    type="radio"
                    [name]="'q' + q.id"
                    [value]="$index"
                    (change)="elegir(q.id, $index)"
                  />
                  <span>{{ opcion }}</span>
                </label>
              }
            </fieldset>
          }
          <button
            type="submit"
            class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large enviar"
            [disabled]="enviando() || !completa(ev)"
          >
            {{ enviando() ? 'Enviando...' : 'Enviar respuestas' }}
          </button>
          @if (errorEnvio()) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">
              No pudimos enviar sus respuestas. Intente de nuevo.
            </div>
          }
        </form>
      }
    </section>
  `,
  styles: [
    `
      .evaluacion {
        padding: 1.5rem 1rem;
        max-width: 560px;
        margin: 0 auto;
      }
      .titulo {
        margin: 0 0 1rem;
      }
      .pregunta {
        border: 1px solid #d0d0d0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0 0 1.25rem;
        background: #fff;
      }
      .enunciado {
        font-size: 1.25rem;
        font-weight: 700;
        padding: 0 0.25rem;
      }
      /* Toda la fila se puede tocar (56 px de alto) y el radio mide 1.5rem. */
      .opcion {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-height: 56px;
        font-size: 1.125rem;
        line-height: 1.4;
        cursor: pointer;
      }
      .opcion input {
        flex: none;
        width: 1.5rem;
        height: 1.5rem;
        accent-color: var(--cima-verde, #0a7d3c);
      }
      .estado {
        font-size: 1.125rem;
        line-height: 1.6;
      }
      .enviar {
        display: block;
        width: 100%;
        margin-top: 0.5rem;
      }
      /* Resultado: verde si aprobó, dorado si debe repasar (no se usa rojo: no es un error). */
      .resultado {
        padding: 1.5rem 1.25rem;
        border-radius: var(--cima-radio, 16px);
        border: 2px solid var(--cima-verde-oscuro, #005c38);
        text-align: center;
      }
      .resultado--ok {
        background: var(--cima-verde-claro, #e6f5ee);
      }
      .resultado--repasar {
        background: #fff8dc;
      }
      .resultado__icono {
        margin: 0;
        font-size: 3rem;
        line-height: 1.2;
      }
      .resultado__titulo {
        margin: 0.25rem 0 0.5rem;
        color: var(--cima-verde-oscuro, #005c38);
      }
      .resultado__aciertos {
        margin: 0 0 0.75rem;
        font-size: 1.25rem;
        font-weight: 700;
      }
      .resultado__texto {
        margin: 0 0 1rem;
        font-size: 1.125rem;
        line-height: 1.5;
      }
      .accion {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        margin-top: 0.75rem;
        text-decoration: none;
      }
    `,
  ],
})
export class AssessmentPageComponent {
  private readonly assessment = inject(AssessmentService);
  private readonly route = inject(ActivatedRoute);

  protected readonly rutaId = this.route.snapshot.paramMap.get('rutaId') ?? '';
  private readonly seleccion = new Map<number, number>();

  readonly cargando = signal<boolean>(true);
  readonly errorCarga = signal<boolean>(false);
  readonly errorEnvio = signal<boolean>(false);
  readonly enviando = signal<boolean>(false);
  readonly evaluacion = signal<Evaluacion | null>(null);
  readonly resultado = signal<ResultadoIntento | null>(null);

  /** Número de preguntas de la evaluación cargada (0 si aún no hay). */
  protected readonly totalPreguntas = computed<number>(
    () => this.evaluacion()?.questions.length ?? 0,
  );

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.errorCarga.set(false);
    try {
      this.evaluacion.set(await this.assessment.obtenerEvaluacion(this.rutaId));
    } catch {
      this.errorCarga.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  elegir(questionId: number, opcion: number): void {
    this.seleccion.set(questionId, opcion);
  }

  /** Verdadero cuando hay una respuesta elegida para cada pregunta. */
  completa(ev: Evaluacion): boolean {
    return ev.questions.every((q) => this.seleccion.has(q.id));
  }

  async enviar(ev: Evaluacion): Promise<void> {
    if (!this.completa(ev)) {
      return;
    }
    this.enviando.set(true);
    this.errorEnvio.set(false);
    const answers = ev.questions.map((q) => ({
      question_id: q.id,
      selected_option: this.seleccion.get(q.id) as number,
    }));
    try {
      this.resultado.set(await this.assessment.enviarRespuestas(this.rutaId, answers));
    } catch {
      this.errorEnvio.set(true);
    } finally {
      this.enviando.set(false);
    }
  }

  /**
   * Maneja el envío del formulario. Se usa el evento nativo `submit` y se evita
   * la acción por defecto: sin `FormsModule`, `(ngSubmit)` nunca se dispara y el
   * navegador recargaría la pantalla en lugar de enviar las respuestas.
   * @param evento evento `submit` del formulario
   * @param ev evaluación mostrada
   */
  protected alEnviar(evento: Event, ev: Evaluacion): void {
    evento.preventDefault();
    void this.enviar(ev);
  }

  /** Vuelve al formulario con las preguntas limpias para un nuevo intento. */
  protected intentarDeNuevo(): void {
    this.seleccion.clear();
    this.errorEnvio.set(false);
    this.resultado.set(null);
  }

  /**
   * Preguntas acertadas, deducidas del puntaje (que el servidor calcula como
   * aciertos sobre el total, redondeado). Es solo informativo: la aprobación la
   * decide el servidor.
   * @param r resultado del intento
   * @returns cantidad de aciertos, entre 0 y el total de preguntas
   */
  protected aciertos(r: ResultadoIntento): number {
    const total = this.totalPreguntas();
    return Math.min(total, Math.max(0, Math.round((r.score * total) / 100)));
  }

  /**
   * Frase con los intentos que le quedan a la persona.
   * @param restantes intentos disponibles antes del enfriamiento
   * @returns texto en singular o plural
   */
  protected textoIntentos(restantes: number): string {
    return restantes === 1
      ? 'Le queda 1 intento.'
      : `Le quedan ${restantes} intentos.`;
  }

  /**
   * Fecha y hora legibles del fin del enfriamiento, en hora de Colombia.
   * @param iso instante en formato ISO-8601 entregado por el servidor
   * @returns frase como "el 25 de noviembre a las 10:30 a. m."; "más tarde" si no es válida
   */
  protected cuando(iso: string): string {
    const fecha = new Date(iso);
    if (Number.isNaN(fecha.getTime())) {
      return 'más tarde';
    }
    const dia = new Intl.DateTimeFormat('es-CO', {
      day: 'numeric',
      month: 'long',
      timeZone: 'America/Bogota',
    }).format(fecha);
    const hora = new Intl.DateTimeFormat('es-CO', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'America/Bogota',
    }).format(fecha);
    return `el ${dia} a las ${hora}`;
  }
}
