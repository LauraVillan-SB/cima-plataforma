# CIMA — Frontend (Angular PWA)

Aplicación Web Progresiva (PWA) ultraligera de CIMA.

## Stack

- Angular (LTS) con Service Worker, HttpClient, RxJS, `inject()`
- Jest + fast-check para pruebas
- Presupuestos de performance: bundle inicial ≤ 500 KB, visita posterior ≤ 50 KB

Dependencias ancladas a versión exacta y resueltas desde JFrog (ver `.npmrc`).

## Puesta en marcha (local)

> El proyecto Angular completo se genera en la Tarea 2 del plan de implementación.
> Este scaffold fija las dependencias y la configuración base.

```bash
npm ci
npm start      # ng serve
npm test       # jest
npm run build  # ng build (PWA)
```

## Convenciones

- Solo UI; la lógica de negocio y la autorización residen en el backend.
- Experiencia voz-first; accesibilidad WCAG 2.1 AA; sin tokens en localStorage.

Especificación completa en `.kiro/specs/cima-plataforma/`.
