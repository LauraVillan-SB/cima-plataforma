import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
} from '@angular/core';
import { NavigationStart, Router } from '@angular/router';
import { filter } from 'rxjs';

import { LectorVozService } from '../voz/lector-voz.service';
import { SELECTOR_BLOQUES, SELECTOR_EXCLUIDOS, bloquesALeer } from './lectura-pagina';

/** Identificador de la lectura de la página en el servicio de voz. */
const ID_LECTURA = 'pagina';

/** Clase global que resalta el bloque que se está leyendo (definida en styles.css). */
const CLASE_LEYENDO = 'cima-leyendo';

/**
 * Botón "Leer esta página" para quien ve poco o prefiere escuchar (Req 13.4, 14.3).
 *
 * Lee con la voz del celular los bloques de texto del contenido principal, uno a uno,
 * resalta el que va diciendo y lo trae a la vista. No necesita conexión ni envía nada:
 * solo lee lo que ya está en pantalla. Al cambiar de pantalla la lectura se detiene.
 * Si el navegador no tiene síntesis de voz, el botón no aparece. Es una ayuda: los
 * lectores de pantalla del sistema (TalkBack, VoiceOver) siguen funcionando igual.
 */
@Component({
  selector: 'cima-lector-pagina',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (lector.disponible) {
      <button
        type="button"
        class="lector"
        data-no-leer
        [attr.aria-pressed]="leyendo()"
        (click)="alternar()"
      >
        <span aria-hidden="true">{{ leyendo() ? '⏹' : '🔊' }}</span>
        {{ leyendo() ? 'Detener' : 'Leer esta página' }}
      </button>
    }
  `,
  styles: [
    `
      .lector {
        position: fixed;
        left: 1rem;
        bottom: 1rem;
        z-index: 20;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        min-height: 56px;
        padding: 0 1.1rem;
        border: 3px solid #fff;
        border-radius: 999px;
        background: var(--cima-verde-oscuro);
        color: #fff;
        font-size: 1.05rem;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
      }
      .lector[aria-pressed='true'] {
        background: #8a1f1f;
      }
    `,
  ],
})
export class LectorPaginaComponent {
  protected readonly lector = inject(LectorVozService);

  protected readonly leyendo = computed(() => this.lector.leyendo() === ID_LECTURA);

  /** Bloques de la lectura en curso, en el mismo orden que los textos enviados a la voz. */
  private bloques: HTMLElement[] = [];
  private resaltado: HTMLElement | null = null;

  constructor() {
    // Resalta y trae a la vista el bloque que se está diciendo.
    effect(() => {
      const indice = this.leyendo() ? this.lector.segmento() : null;
      this.resaltar(indice === null ? null : (this.bloques[indice] ?? null));
    });
    // Al cambiar de pantalla se detiene: el texto que se leía ya no está.
    const navegacion = inject(Router)
      .events.pipe(filter((evento) => evento instanceof NavigationStart))
      .subscribe(() => this.detenerSiLee());
    inject(DestroyRef).onDestroy(() => {
      navegacion.unsubscribe();
      this.detenerSiLee();
    });
  }

  protected alternar(): void {
    if (this.leyendo()) {
      this.lector.detener();
      return;
    }
    this.bloques = this.bloquesDeLaPagina();
    this.lector.leerPorPartes(
      ID_LECTURA,
      this.bloques.map((bloque) => bloque.innerText),
    );
  }

  private bloquesDeLaPagina(): HTMLElement[] {
    const contenido = document.getElementById('contenido');
    if (!contenido) {
      return [];
    }
    const visibles = Array.from(contenido.querySelectorAll<HTMLElement>(SELECTOR_BLOQUES)).filter(
      (el) => !el.closest(SELECTOR_EXCLUIDOS) && el.getClientRects().length > 0,
    );
    return bloquesALeer(
      visibles,
      (el) => el.innerText,
      (padre, hijo) => padre.contains(hijo),
    );
  }

  private resaltar(bloque: HTMLElement | null): void {
    this.resaltado?.classList.remove(CLASE_LEYENDO);
    this.resaltado = bloque;
    if (bloque) {
      bloque.classList.add(CLASE_LEYENDO);
      bloque.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  private detenerSiLee(): void {
    if (this.leyendo()) {
      this.lector.detener();
    }
    this.resaltar(null);
    this.bloques = [];
  }
}
