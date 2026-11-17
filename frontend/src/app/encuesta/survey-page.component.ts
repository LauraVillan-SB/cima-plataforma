import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { generarClaveIdempotencia } from '../core/idempotencia';
import { UserContextService } from '../core/user-context.service';
import {
  COMENTARIO_MAX,
  MENSAJE_SIN_ENCUESTA,
  OPCIONES_CALIFICACION,
  armarRespuesta,
  calificacionValida,
  mensajeError,
  preguntaDeTipo,
} from './encuesta';
import { PresentacionEncuesta, SurveyService } from './survey.service';

/** Identificador de ruta con forma de UUID; si no la tiene no se llama al backend. */
const PATRON_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Encuesta de satisfacción de una ruta completada (Req 20.1, 20.2, 20.7).
 *
 * Breve y opcional: una calificación de 1 a 5 con botones grandes y un comentario
 * opcional. "Ahora no" vuelve a la ruta sin bloquear nada. Si ya respondió, solo
 * agradece. El comentario se puede dictar con el micrófono del teclado del celular,
 * y el backend le quita los datos personales antes de guardarlo (Req 20.5). La clave
 * de idempotencia se genera una vez, así que reintentar no duplica (Req 20.6).
 */
@Component({
  selector: 'cima-survey-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="encuesta">
      <h1 class="titulo">Tu opinión</h1>

      @if (cargando()) {
        <p role="status" aria-live="polite">Cargando la encuesta...</p>
      } @else if (errorCarga(); as mensaje) {
        <div class="sb-ui-alert sb-ui-alert--info" role="status">{{ mensaje }}</div>
        <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large enlace">
          Volver a mi ruta
        </a>
      } @else if (enviada() || encuesta()?.already_answered) {
        <div class="gracias" role="status" aria-live="polite">
          <p class="gracias__titulo">¡Gracias por contarnos!</p>
          <p>Tu opinión nos ayuda a mejorar la Escuela.</p>
        </div>
        <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large enlace">
          Volver a mi ruta
        </a>
      } @else if (encuesta()) {
        <p class="intro">Son solo dos preguntas y la segunda es opcional.</p>
        <form (submit)="$event.preventDefault(); enviar()">
          <fieldset class="pregunta">
            <legend class="enunciado">{{ textoCalificacion() }}</legend>
            <div class="escala">
              @for (o of opciones; track o.valor) {
                <label class="opcion" [class.opcion--elegida]="calificacion() === o.valor">
                  <input
                    type="radio"
                    name="calificacion"
                    [value]="o.valor"
                    [checked]="calificacion() === o.valor"
                    (change)="calificacion.set(o.valor)"
                  />
                  <span class="opcion__numero">{{ o.valor }}</span>
                  <span class="opcion__texto">{{ o.etiqueta }}</span>
                </label>
              }
            </div>
          </fieldset>

          @if (textoComentario(); as enunciado) {
            <label class="enunciado" for="comentario">{{ enunciado }}</label>
            <textarea
              id="comentario"
              class="comentario"
              rows="4"
              [maxLength]="comentarioMax"
              [value]="comentario()"
              (input)="comentario.set($any($event.target).value)"
              aria-describedby="ayuda-comentario"
            ></textarea>
            <p id="ayuda-comentario" class="ayuda">
              Puedes dictarlo con el micrófono del teclado de tu celular.
              {{ comentario().length }} de {{ comentarioMax }} letras.
            </p>
          }

          @if (errorEnvio(); as mensaje) {
            <div class="sb-ui-alert sb-ui-alert--error" role="alert">{{ mensaje }}</div>
          }

          <button
            type="submit"
            class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large enlace"
            [disabled]="!puedeEnviar()"
          >
            {{ enviando() ? 'Enviando...' : 'Enviar mi opinión' }}
          </button>
          <a routerLink="/mi-ruta" class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large enlace">
            Ahora no
          </a>
        </form>
      }
    </section>
  `,
  styles: [
    `
      .encuesta { padding: 1.5rem 1rem; max-width: 560px; margin: 0 auto; font-size: 1.125rem; }
      .titulo { margin: 0 0 0.5rem; }
      .intro { margin: 0 0 1rem; color: var(--cima-texto-suave); }
      .pregunta { border: 0; padding: 0; margin: 0 0 1.25rem; }
      .enunciado { display: block; font-weight: 700; line-height: 1.4; margin-bottom: 0.75rem; }
      .escala { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.5rem; }
      .opcion {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        min-height: 72px;
        padding: 0.5rem 0.25rem;
        border: 2px solid var(--cima-borde);
        border-radius: 12px;
        background: #fff;
        cursor: pointer;
        text-align: center;
      }
      .opcion input { position: absolute; opacity: 0; width: 1px; height: 1px; }
      .opcion:focus-within { outline: 3px solid var(--cima-dorado); outline-offset: 2px; }
      .opcion--elegida { border-color: var(--cima-verde-oscuro); background: var(--cima-verde-claro); }
      .opcion__numero { font-size: 1.5rem; font-weight: 700; color: var(--cima-verde-oscuro); }
      .opcion__texto { font-size: 0.95rem; line-height: 1.2; }
      .comentario {
        width: 100%;
        box-sizing: border-box;
        font-size: 1.05rem;
        padding: 0.5rem;
        border: 2px solid var(--cima-verde-oscuro);
        border-radius: 8px;
      }
      .ayuda { margin: 0.25rem 0 1rem; font-size: 0.95rem; color: var(--cima-texto-suave); }
      .enlace { display: inline-flex; align-items: center; justify-content: center; width: 100%; margin-top: 0.75rem; text-decoration: none; }
      .gracias { background: var(--cima-verde-claro); border-radius: var(--cima-radio); padding: 1.25rem; text-align: center; }
      .gracias__titulo { font-size: 1.35rem; font-weight: 700; color: var(--cima-verde-oscuro); margin: 0 0 0.5rem; }
    `,
  ],
})
export class SurveyPageComponent {
  private readonly servicio = inject(SurveyService);
  private readonly usuario = inject(UserContextService);
  private readonly rutaId = inject(ActivatedRoute).snapshot.paramMap.get('rutaId') ?? '';

  /** Una sola clave por pantalla: reintentar el envío no duplica la respuesta. */
  private readonly claveEvento = generarClaveIdempotencia();

  readonly opciones = OPCIONES_CALIFICACION;
  readonly comentarioMax = COMENTARIO_MAX;

  readonly cargando = signal<boolean>(true);
  readonly errorCarga = signal<string | null>(null);
  readonly encuesta = signal<PresentacionEncuesta | null>(null);
  readonly calificacion = signal<number | null>(null);
  readonly comentario = signal<string>('');
  readonly enviando = signal<boolean>(false);
  readonly enviada = signal<boolean>(false);
  readonly errorEnvio = signal<string | null>(null);

  readonly textoCalificacion = computed(
    () => preguntaDeTipo(this.encuesta()?.questions ?? [], 'rating')?.text ?? '¿Qué tanto te sirvió esta ruta?',
  );
  readonly textoComentario = computed(
    () => preguntaDeTipo(this.encuesta()?.questions ?? [], 'text')?.text ?? null,
  );
  readonly puedeEnviar = computed(
    () => !this.enviando() && calificacionValida(this.calificacion()) && this.usuario.perfil() !== null,
  );

  constructor() {
    void this.cargar();
  }

  async cargar(): Promise<void> {
    if (!PATRON_UUID.test(this.rutaId)) {
      this.errorCarga.set(MENSAJE_SIN_ENCUESTA);
      this.cargando.set(false);
      return;
    }
    try {
      this.encuesta.set(await this.servicio.obtener(this.rutaId));
    } catch (e: unknown) {
      if (!(e instanceof HttpErrorResponse)) {
        throw e;
      }
      this.errorCarga.set(mensajeError(e.status, e.error?.detail));
    } finally {
      this.cargando.set(false);
    }
  }

  async enviar(): Promise<void> {
    const perfil = this.usuario.perfil();
    const calificacion = this.calificacion();
    if (!this.puedeEnviar() || !perfil || !calificacionValida(calificacion)) {
      return;
    }
    this.enviando.set(true);
    this.errorEnvio.set(null);
    try {
      await this.servicio.responder(
        this.rutaId,
        armarRespuesta(this.claveEvento, perfil, calificacion, this.comentario()),
      );
      this.enviada.set(true);
    } catch (e: unknown) {
      if (!(e instanceof HttpErrorResponse)) {
        throw e;
      }
      this.errorEnvio.set(mensajeError(e.status, e.error?.detail));
    } finally {
      this.enviando.set(false);
    }
  }
}
