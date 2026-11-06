import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

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
 */
@Component({
  selector: 'cima-assessment-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="evaluacion">
      <h1 class="titulo">Evaluación</h1>

      @if (cargando()) {
        <p class="estado" role="status" aria-live="polite">Cargando la evaluación...</p>
      } @else if (errorCarga()) {
        <div class="sb-ui-alert sb-ui-alert--error" role="alert">
          No pudimos cargar la evaluación. Revisa tu conexión e intenta de nuevo.
        </div>
      } @else if (resultado(); as r) {
        <div
          class="sb-ui-alert"
          [class.sb-ui-alert--success]="r.passed"
          [class.sb-ui-alert--warning]="!r.passed"
          role="status"
        >
          @if (r.passed) {
            <p>¡Aprobaste! Tu puntaje fue {{ r.score }} de 100.</p>
          } @else {
            <p>Tu puntaje fue {{ r.score }} de 100. Aún no alcanzas el mínimo.</p>
            @if (r.cooldown_until) {
              <p>Agotaste tus intentos por ahora. Podrás volver a intentarlo más tarde.</p>
            } @else {
              <p>Te quedan {{ r.attempts_remaining }} intento(s).</p>
            }
          }
        </div>
      } @else if (evaluacion(); as ev) {
        <form (ngSubmit)="enviar(ev)">
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
            class="sb-ui-button sb-ui-button--primary sb-ui-button--fill sb-ui-button--large enviar"
            [disabled]="enviando() || !completa(ev)"
          >
            {{ enviando() ? 'Enviando...' : 'Enviar respuestas' }}
          </button>
          @if (errorEnvio()) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">
              No pudimos enviar tus respuestas. Intenta de nuevo.
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
    `,
  ],
})
export class AssessmentPageComponent {
  private readonly assessment = inject(AssessmentService);
  private readonly route = inject(ActivatedRoute);

  private readonly rutaId = this.route.snapshot.paramMap.get('rutaId') ?? '';
  private readonly seleccion = new Map<number, number>();

  readonly cargando = signal<boolean>(true);
  readonly errorCarga = signal<boolean>(false);
  readonly errorEnvio = signal<boolean>(false);
  readonly enviando = signal<boolean>(false);
  readonly evaluacion = signal<Evaluacion | null>(null);
  readonly resultado = signal<ResultadoIntento | null>(null);

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
}
