import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LearningService, Ruta } from '../aprendizaje/learning.service';
import { etiquetaTema, iconoTema, minutos } from '../aprendizaje/temas';
import { UserContextService } from '../core/user-context.service';
import { GamificationService } from '../gamificacion/gamification.service';
import { elegirSiguientePaso, sumarAvance } from './siguiente-paso';

/** Temas que enseña CIMA, presentados como los ejes de la página de sostenibilidad. */
const TEMAS: readonly { readonly codigo: string; readonly texto: string }[] = [
  { codigo: 'finanzas', texto: 'Organice su plata, ahorre para lo que viene y evite las deudas caras.' },
  { codigo: 'gestion_riesgos', texto: 'Prepárese ante lo inesperado y proteja lo que ha construido.' },
  { codigo: 'adaptacion_clima', texto: 'Cuide su cultivo o su negocio ante lluvias, sequías y calor.' },
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
        @if (contexto.comoLlamar(); as nombre) {
          <p class="portada__saludo">Hola, {{ nombre }}</p>
        } @else {
          <a class="portada__enlace" routerLink="/perfil">¿Cómo quiere que le digamos?</a>
        }
        <h1 class="portada__titulo">
          @if (contexto.actividadFrase(); as frase) {
            Aprenda a proteger {{ frase }}
          } @else {
            Aprenda a proteger lo que ha construido
          }
        </h1>
        <p class="portada__texto">
          Lecciones cortas para cuidar su plata, prevenir riesgos y adaptarse al clima.
          Porque cuando está en calma, también progresa.
        </p>
      </header>

      @if (!contexto.cargando() && !contexto.perfil()) {
        <div class="sb-ui-alert sb-ui-alert--info aviso" role="status">
          <p>Cuéntenos a qué se dedica y le mostramos la ruta que más le sirve.</p>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton" routerLink="/perfil">
            Completar mi perfil
          </a>
        </div>
      }

      <section class="bloque" aria-labelledby="titulo-paso">
        <h2 id="titulo-paso" class="bloque__titulo">Su siguiente paso</h2>
        @if (cargando()) {
          <p role="status" aria-live="polite">Buscando su siguiente lección...</p>
        } @else if (error()) {
          <div class="sb-ui-alert sb-ui-alert--error" role="alert">
            No pudimos cargar su ruta. Revise su conexión e intente de nuevo.
          </div>
          <button type="button" class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke boton" (click)="cargar()">
            Reintentar
          </button>
        } @else {
          @let p = paso();
          @if (p.tipo === 'leccion') {
            <p class="paso__ruta">{{ p.ruta.title ?? 'Su ruta de aprendizaje' }}</p>
            <p class="paso__leccion">{{ p.item.capsule.title ?? etiqueta(p.item.capsule.topic) }}</p>
            <p class="paso__meta">
              {{ etiqueta(p.item.capsule.topic) }} · {{ mins(p.item.capsule.duration_sec) }} min ·
              lección {{ p.item.position }} de {{ p.ruta.total_count }}
            </p>
            <div class="barra" role="progressbar" [attr.aria-label]="'Avance en ' + (p.ruta.title ?? 'su ruta')"
                 [attr.aria-valuenow]="pct(p.ruta)" aria-valuemin="0" aria-valuemax="100">
              <div class="barra__relleno" [style.width.%]="pct(p.ruta)"></div>
            </div>
            <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton"
               [routerLink]="['/aprendizaje/leccion', p.ruta.path_id, p.item.capsule.id]">
              <i class="fa-solid fa-play icono-boton" aria-hidden="true"></i>
              {{ p.ruta.completed_count === 0 ? 'Empezar la lección' : 'Continuar la lección' }}
            </a>
          } @else if (p.tipo === 'evaluacion') {
            <p class="paso__leccion">Terminó las lecciones de {{ p.ruta.title ?? 'su ruta' }}</p>
            <p class="paso__meta">Presente la evaluación para obtener su certificado.</p>
            <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton"
               [routerLink]="['/evaluacion', p.ruta.path_id]">
              <i class="fa-solid fa-clipboard-check icono-boton" aria-hidden="true"></i>
              Presentar la evaluación
            </a>
          } @else if (p.tipo === 'completo') {
            <p class="paso__leccion">¡Completó todas sus rutas!</p>
            <p class="paso__meta">Puede repasar las lecciones cuando quiera.</p>
          } @else {
            <p class="paso__meta">Pronto tendrá una ruta de aprendizaje para usted.</p>
          }
          <a class="enlace" routerLink="/mi-ruta">
            <i class="fa-solid fa-route icono-boton" aria-hidden="true"></i>
            Ver toda mi ruta
          </a>
        }
      </section>

      @if (!cargando() && !error() && avance().total > 0) {
        <section class="bloque" aria-labelledby="titulo-avance">
          <h2 id="titulo-avance" class="bloque__titulo">Su avance</h2>
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
                    <br />Le faltan {{ n.points_needed }} para el nivel {{ n.name }}.
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
            <h3 class="pasos__titulo">Aprenda en lecciones cortas</h3>
            <p>De 3 a 5 minutos cada una, en el orden de su ruta y a su ritmo.</p>
          </li>
          <li class="pasos__item">
            <span class="pasos__numero pasos__numero--2" aria-hidden="true">2.</span>
            <h3 class="pasos__titulo">Presente la evaluación</h3>
            <p>Al terminar la ruta responde unas preguntas sencillas.</p>
          </li>
          <li class="pasos__item">
            <span class="pasos__numero pasos__numero--3" aria-hidden="true">3.</span>
            <h3 class="pasos__titulo">Reciba su certificado</h3>
            <p>Y en el camino gana puntos e insignias por lo que aprende.</p>
          </li>
        </ol>
      </section>

      <section class="bloque" aria-labelledby="titulo-temas">
        <h2 id="titulo-temas" class="bloque__titulo">Lo que aprende</h2>
        <ul class="temas">
          @for (t of temas; track t.codigo) {
            <li class="tema">
              <h3 class="tema__titulo">
                <i class="fa-solid {{ icono(t.codigo) }} tema__icono" aria-hidden="true"></i>
                {{ etiqueta(t.codigo) }}
              </h3>
              <p>{{ t.texto }}</p>
            </li>
          }
        </ul>
      </section>

      <!-- En un bloque blanco: los botones con borde son transparentes y sobre el
           fondo gris de la página su texto quedaba en 4,42:1 (Req 13.2). -->
      <section class="bloque" aria-labelledby="titulo-atajos">
        <h2 id="titulo-atajos" class="bloque__titulo">¿Qué más quiere hacer?</h2>
        <div class="atajos">
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--fill sb-ui-button--large boton" routerLink="/asistente">
            <i class="fa-solid fa-comments icono-boton" aria-hidden="true"></i>
            Hablar con mi asistente
          </a>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large boton" routerLink="/logros">
            <i class="fa-solid fa-trophy icono-boton" aria-hidden="true"></i>
            Ver mis logros
          </a>
          <a class="sb-ui-button sb-ui-button--secondary sb-ui-button--stroke sb-ui-button--large boton" routerLink="/ranking">
            <i class="fa-solid fa-ranking-star icono-boton" aria-hidden="true"></i>
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
      .portada__saludo { margin: 0 0 0.5rem; font-size: 1.25rem; font-weight: 700; }
      .portada__enlace {
        display: inline-flex; align-items: center; min-height: 44px; margin-bottom: 0.25rem;
        color: #fff; font-weight: 700; text-decoration: underline;
      }
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
      .tema__titulo { color: var(--cima-verde-oscuro); display: flex; align-items: center; gap: 0.5rem; }
      .tema__icono { font-size: 1.4rem; }
      .icono-boton { margin-right: 0.5rem; }
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

  protected icono(topic: string): string {
    return iconoTema(topic);
  }

  protected pct(ruta: Ruta): number {
    return ruta.total_count === 0 ? 0 : Math.round((ruta.completed_count / ruta.total_count) * 100);
  }
}
