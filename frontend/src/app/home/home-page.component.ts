import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LearningService, Ruta } from '../aprendizaje/learning.service';
import { etiquetaTema, minutos } from '../aprendizaje/temas';
import { UserContextService } from '../core/user-context.service';
import { GamificationService } from '../gamificacion/gamification.service';
import { elegirSiguientePaso, sumarAvance } from './siguiente-paso';

/** Temas que enseña CIMA, presentados como los ejes de la página de sostenibilidad. */
const TEMAS: readonly { readonly codigo: string; readonly texto: string }[] = [
  { codigo: 'finanzas', texto: 'Organiza tu plata, ahorra para lo que viene y evita las deudas caras.' },
  { codigo: 'gestion_riesgos', texto: 'Prepárate ante lo inesperado y protege lo que has construido.' },
  { codigo: 'adaptacion_clima', texto: 'Cuida tu cultivo o tu negocio ante lluvias, sequías y calor.' },
];

/**
 * Pantalla de inicio tras entrar. Muestra de primera vista lo útil: el siguiente
 * paso de la ruta de aprendizaje, el avance y el nivel, cómo funciona CIMA y qué
 * se aprende. El estilo y el tono siguen la página de sostenibilidad de Seguros
 * Bolívar (portada verde con título amarillo, bloques con números grandes,
 * botones en píldora). Las microcápsulas se abren solo desde la ruta, en orden.
 * Solo presentación: el avance, el nivel y los puntos los calcula el backend
 * (Req 17.3, 19.3); el Perfil llega sin PII en claro (Req 9.4).
 */
@Component({
  selector: 'cima-home-page',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="inicio">
      <header class="portada">
        <p class="portada__escuela">Escuela de Sostenibilidad e Inclusión</p>
        <h1 class="portada__titulo">
          @if (contexto.actividadFrase(); as frase) {
            Aprende a proteger {{ frase }}
          } @else {
            Aprende a proteger lo que has construido
          }
        </h1>
        <p class="portada__texto">
          Lecciones cortas para cuidar tu plata, prevenir riesgos y adaptarte al clima.
          Porque cuando estás tranquilo, también progresas.
        </p>
      </header>

      @if (!contexto.cargando() && !contexto.perfil()) {
        <div class="sb-ui-alert sb-ui-alert--info aviso" role="status">
          <p>Cuéntanos a qué te dedicas y te mostramos la ruta que más te sirve.</p>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton" routerLink="/perfil">
            Completar mi perfil
          </a>
        </div>
      }

      <section class="bloque" aria-labelledby="titulo-paso">
        <h2 id="titulo-paso" class="bloque__titulo">Tu siguiente paso</h2>
        @if (cargando()) {
          <p role="status" aria-live="polite">Buscando tu siguiente lección...</p>
        } @else if (error()) {
          <div class="sb-ui-alert sb-ui-alert--error" role="alert">
            No pudimos cargar tu ruta. Revisa tu conexión e intenta de nuevo.
          </div>
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton" (click)="cargar()">
            Reintentar
          </button>
        } @else {
          @let p = paso();
          @if (p.tipo === 'leccion') {
            <p class="paso__ruta">{{ p.ruta.title ?? 'Tu ruta de aprendizaje' }}</p>
            <p class="paso__leccion">{{ p.item.capsule.title ?? etiqueta(p.item.capsule.topic) }}</p>
            <p class="paso__meta">
              {{ etiqueta(p.item.capsule.topic) }} · {{ mins(p.item.capsule.duration_sec) }} min ·
              lección {{ p.item.position }} de {{ p.ruta.total_count }}
            </p>
            <div class="barra" role="progressbar" [attr.aria-label]="'Avance en ' + (p.ruta.title ?? 'tu ruta')"
                 [attr.aria-valuenow]="pct(p.ruta)" aria-valuemin="0" aria-valuemax="100">
              <div class="barra__relleno" [style.width.%]="pct(p.ruta)"></div>
            </div>
            <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton"
               [routerLink]="['/aprendizaje/leccion', p.ruta.path_id, p.item.capsule.id]">
              {{ p.ruta.completed_count === 0 ? 'Empezar la lección' : 'Continuar la lección' }}
            </a>
          } @else if (p.tipo === 'evaluacion') {
            <p class="paso__leccion">Terminaste las lecciones de {{ p.ruta.title ?? 'tu ruta' }}</p>
            <p class="paso__meta">Presenta la evaluación para obtener tu certificado.</p>
            <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton"
               [routerLink]="['/evaluacion', p.ruta.path_id]">
              Presentar la evaluación
            </a>
          } @else if (p.tipo === 'completo') {
            <p class="paso__leccion">¡Completaste todas tus rutas!</p>
            <p class="paso__meta">Puedes repasar las lecciones cuando quieras.</p>
          } @else {
            <p class="paso__meta">Pronto tendrás una ruta de aprendizaje para ti.</p>
          }
          <a class="enlace" routerLink="/mi-ruta">Ver toda mi ruta</a>
        }
      </section>

      @if (!cargando() && !error() && avance().total > 0) {
        <section class="bloque" aria-labelledby="titulo-avance">
          <h2 id="titulo-avance" class="bloque__titulo">Tu avance</h2>
          <ul class="cifras">
            <li class="cifra">
              <span class="cifra__numero">{{ avance().terminadas }}</span>
              <span class="cifra__texto">de {{ avance().total }} lecciones terminadas</span>
            </li>
            @if (gamificacion.resumen(); as r) {
              <li class="cifra">
                <span class="cifra__numero">{{ r.total_points }}</span>
                <span class="cifra__texto">
                  puntos · nivel {{ r.level.name }}
                  @if (r.next_level; as n) {
                    <br />Te faltan {{ n.points_needed }} para el nivel {{ n.name }}.
                  }
                </span>
              </li>
              <li class="cifra">
                <span class="cifra__numero">{{ insigniasGanadas() }}</span>
                <span class="cifra__texto">{{ insigniasGanadas() === 1 ? 'insignia ganada' : 'insignias ganadas' }}</span>
              </li>
            }
          </ul>
        </section>
      }

      <section class="bloque" aria-labelledby="titulo-como">
        <h2 id="titulo-como" class="bloque__titulo">Así funciona CIMA</h2>
        <ol class="pasos">
          <li class="pasos__item">
            <span class="pasos__numero pasos__numero--1" aria-hidden="true">1.</span>
            <h3 class="pasos__titulo">Aprende en lecciones cortas</h3>
            <p>De 3 a 5 minutos cada una, en el orden de tu ruta y a tu ritmo.</p>
          </li>
          <li class="pasos__item">
            <span class="pasos__numero pasos__numero--2" aria-hidden="true">2.</span>
            <h3 class="pasos__titulo">Presenta la evaluación</h3>
            <p>Al terminar la ruta respondes unas preguntas sencillas.</p>
          </li>
          <li class="pasos__item">
            <span class="pasos__numero pasos__numero--3" aria-hidden="true">3.</span>
            <h3 class="pasos__titulo">Recibe tu certificado</h3>
            <p>Y en el camino ganas puntos e insignias por lo que aprendes.</p>
          </li>
        </ol>
      </section>

      <section class="bloque" aria-labelledby="titulo-temas">
        <h2 id="titulo-temas" class="bloque__titulo">Lo que aprendes</h2>
        <ul class="temas">
          @for (t of temas; track t.codigo) {
            <li class="tema">
              <h3 class="tema__titulo">{{ etiqueta(t.codigo) }}</h3>
              <p>{{ t.texto }}</p>
            </li>
          }
        </ul>
      </section>

      <!-- En un bloque blanco: los botones con borde son transparentes y sobre el
           fondo gris de la página su texto quedaba en 4,42:1 (Req 13.2). -->
      <section class="bloque" aria-labelledby="titulo-atajos">
        <h2 id="titulo-atajos" class="bloque__titulo">¿Qué más quieres hacer?</h2>
        <div class="atajos">
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton" routerLink="/asistente">
            Hablar con mi asistente
          </a>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large boton" routerLink="/logros">
            Ver mis logros
          </a>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large boton" routerLink="/ranking">
            Ver el ranking
          </a>
        </div>
      </section>
    </div>
  `,
  styles: [
    `
      .inicio { max-width: 960px; margin: 0 auto; padding: 1rem; display: grid; gap: 1.25rem; }
      /* Solo verdes oscuros: el blanco queda sobre 7,5:1 y el amarillo sobre 5,8:1 (Req 13.2). */
      .portada {
        border-radius: 20px; padding: 1.75rem 1.5rem; color: #fff;
        background-color: var(--cima-verde-oscuro);
        background-image: linear-gradient(160deg, #0b613e 0%, var(--cima-verde-oscuro) 55%, #00432a 100%);
      }
      .portada__escuela { margin: 0 0 0.5rem; font-weight: 700; font-size: 0.95rem; }
      .portada__titulo { margin: 0 0 0.75rem; color: var(--cima-dorado); font-size: 1.6rem; line-height: 1.25; }
      .portada__texto { margin: 0; font-size: 1.1rem; line-height: 1.5; }
      .aviso p { margin: 0 0 0.75rem; }
      .bloque { background: var(--cima-superficie); border: 1px solid var(--cima-borde); border-radius: 20px; padding: 1.5rem; }
      .bloque__titulo { margin: 0 0 1rem; color: var(--cima-verde-oscuro); font-size: 1.35rem; }
      .paso__ruta { margin: 0; color: var(--cima-texto-suave); font-weight: 700; }
      .paso__leccion { margin: 0.25rem 0; font-size: 1.25rem; font-weight: 700; color: var(--cima-texto); }
      .paso__meta { margin: 0 0 0.75rem; color: var(--cima-texto-suave); }
      .barra { background: var(--cima-verde-claro); border-radius: 999px; height: 12px; overflow: hidden; margin-bottom: 1rem; }
      .barra__relleno { background: var(--cima-verde); height: 100%; }
      .boton { display: flex; align-items: center; justify-content: center; width: 100%; text-decoration: none; margin-bottom: 0.75rem; }
      .enlace { display: inline-flex; align-items: center; min-height: 44px; color: var(--cima-verde-oscuro); font-weight: 700; }
      .cifras, .pasos, .temas { list-style: none; margin: 0; padding: 0; display: grid; gap: 1rem; }
      .cifra { display: flex; align-items: baseline; gap: 0.75rem; }
      .cifra__numero { font-size: 2.25rem; font-weight: 700; color: var(--cima-verde-oscuro); min-width: 1.6ch; }
      .cifra__texto { color: var(--cima-texto); }
      .pasos__item { border-left: 3px solid var(--cima-verde); padding-left: 1rem; }
      .pasos__numero { display: block; font-size: 2.5rem; font-weight: 700; line-height: 1; }
      .pasos__numero--1 { color: var(--cima-verde-oscuro); }
      .pasos__numero--2 { color: var(--cima-verde); }
      .pasos__numero--3 { color: var(--cima-texto); }
      .pasos__titulo, .tema__titulo { margin: 0.25rem 0; font-size: 1.15rem; }
      .pasos__item p, .tema p { margin: 0; color: var(--cima-texto-suave); }
      .tema { background: var(--cima-fondo); border-radius: var(--cima-radio); padding: 1rem; }
      .tema__titulo { color: var(--cima-verde-oscuro); }
      .atajos { display: grid; }
      @media (min-width: 720px) {
        .portada { padding: 2.5rem; }
        .portada__titulo { font-size: 2rem; }
        .pasos, .temas, .cifras { grid-template-columns: repeat(3, 1fr); }
        .atajos { grid-template-columns: repeat(3, 1fr); column-gap: 0.75rem; }
      }
    `,
  ],
})
export class HomePageComponent {
  private readonly learning = inject(LearningService);

  protected readonly contexto = inject(UserContextService);
  protected readonly gamificacion = inject(GamificationService);
  protected readonly temas = TEMAS;

  protected readonly cargando = signal<boolean>(true);
  protected readonly error = signal<boolean>(false);
  private readonly rutas = signal<readonly Ruta[]>([]);

  protected readonly paso = computed(() => elegirSiguientePaso(this.rutas()));
  protected readonly avance = computed(() => sumarAvance(this.rutas()));
  protected readonly insigniasGanadas = computed(
    () => this.gamificacion.resumen()?.badges.filter((b) => b.earned).length ?? 0,
  );

  constructor() {
    void this.cargar();
  }

  protected async cargar(): Promise<void> {
    this.cargando.set(true);
    this.error.set(false);
    try {
      this.rutas.set(await this.learning.obtenerRutas());
    } catch {
      // Mensaje genérico para el Usuario; el detalle lo registra el backend.
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  protected etiqueta(topic: string): string {
    return etiquetaTema(topic);
  }

  protected mins(segundos: number): number {
    return minutos(segundos);
  }

  protected pct(ruta: Ruta): number {
    return ruta.total_count === 0 ? 0 : Math.round((ruta.completed_count / ruta.total_count) * 100);
  }
}
