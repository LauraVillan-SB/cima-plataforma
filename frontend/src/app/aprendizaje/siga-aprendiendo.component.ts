import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { NetworkStatusService } from '../core/network-status.service';

/** Recurso externo gratuito y oficial para seguir aprendiendo de tecnología. */
export interface RecursoExterno {
  readonly titulo: string;
  readonly descripcion: string;
  readonly url: string;
}

/**
 * Identificador de la "Ruta: la tecnología a su favor". Sale de `uuid5` con el slug
 * `ruta-tecnologia-a-su-favor` en el catálogo del backend, así que es estable.
 */
export const RUTA_TECNOLOGIA_ID = 'de010b6f-e813-5d8e-bbbd-8f717fad0aca';

/**
 * Enlaces fijos a sitios oficiales (allowlist): el cliente nunca arma estas direcciones
 * ni las recibe de otro lado. Se revisaron a mano el 24/11/2026; revisarlas cada año.
 */
export const RECURSOS_TECNOLOGIA: readonly RecursoExterno[] = [
  {
    titulo: 'Conceptos básicos de la nube (AWS)',
    descripcion: 'Página gratuita de Amazon Web Services, en español y sin registrarse.',
    url: 'https://aws.amazon.com/es/getting-started/cloud-essentials/',
  },
  {
    titulo: 'Ciudadanía Digital (MinTIC)',
    descripcion: 'Cursos gratuitos del Ministerio TIC en competencias digitales, con certificado.',
    url: 'https://www.mintic.gov.co/portal/inicio/Sala-de-prensa/Noticias/101721:Conviertase-en-un-ciudadano-digital-con-33-cursos-gratuitos',
  },
  {
    titulo: 'Cursos virtuales del SENA',
    descripcion: 'Oferta de cursos gratuitos del SENA para estudiar desde el celular.',
    url: 'https://betowa.sena.edu.co/oferta',
  },
];

/**
 * "Siga aprendiendo": accesos a recursos oficiales gratuitos al final de las lecciones
 * de la ruta de tecnología. Abren en otra pestaña sin compartir la página de CIMA
 * (`noopener noreferrer`). Sin conexión se avisa que necesitan internet.
 */
@Component({
  selector: 'cima-siga-aprendiendo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="siga" aria-labelledby="siga-titulo">
      <h2 id="siga-titulo" class="siga__titulo">Siga aprendiendo</h2>
      <p class="siga__texto">Cursos y páginas gratuitas de entidades oficiales. Se abren en otra pestaña.</p>
      @if (!red.online()) {
        <div class="sb-ui-alert sb-ui-alert--info" role="status">
          Estos enlaces necesitan internet. Puede abrirlos cuando tenga conexión.
        </div>
      }
      <ul class="siga__lista">
        @for (r of recursos; track r.url) {
          <li>
            <a class="siga__enlace" [href]="r.url" target="_blank" rel="noopener noreferrer"
               [attr.aria-label]="r.titulo + ' (se abre en otra pestaña)'">
              <svg class="siga__icono" viewBox="0 0 24 24" width="28" height="28" aria-hidden="true" focusable="false">
                <path fill="currentColor" d="M12 3 1 9l11 6 9-4.9V17h2V9L12 3zm-7 9.2V16c0 1.7 3.1 3.5 7 3.5s7-1.8 7-3.5v-3.8l-7 3.8-7-3.8z" />
              </svg>
              <span class="siga__cuerpo">
                <span class="siga__nombre">{{ r.titulo }}</span>
                <span class="siga__descripcion">{{ r.descripcion }}</span>
              </span>
              <svg class="siga__salida" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
                <path fill="currentColor" d="M14 3v2h3.6l-9.8 9.8 1.4 1.4L19 6.4V10h2V3h-7zM5 5h6V3H5a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h14a2 2 0 0 0 2-2v-6h-2v6H5V5z" />
              </svg>
            </a>
          </li>
        }
      </ul>
    </section>
  `,
  styles: [
    `
      .siga { border: 1px solid var(--cima-verde); border-radius: var(--cima-radio); padding: 1rem; margin-bottom: 1rem; }
      .siga__titulo { margin: 0 0 0.25rem; font-size: 1.25rem; color: var(--cima-verde-oscuro); }
      .siga__texto { margin: 0 0 0.75rem; color: var(--cima-texto-suave); }
      .siga__lista { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
      .siga__enlace { display: flex; align-items: center; gap: 0.75rem; min-height: 44px; padding: 0.75rem; border-radius: 8px; background: var(--cima-verde-claro); color: var(--cima-verde-oscuro); text-decoration: none; }
      .siga__enlace:focus-visible { outline: 3px solid var(--cima-verde-oscuro); outline-offset: 2px; }
      .siga__icono, .siga__salida { flex: none; }
      .siga__cuerpo { display: flex; flex-direction: column; flex: 1; }
      .siga__nombre { font-weight: 700; }
      .siga__descripcion { font-size: 0.95rem; }
    `,
  ],
})
export class SigaAprendiendoComponent {
  protected readonly red = inject(NetworkStatusService);
  protected readonly recursos = RECURSOS_TECNOLOGIA;
}
