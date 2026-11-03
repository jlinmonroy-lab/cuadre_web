# ADR-0002 · Frontend: Next.js (App Router), TypeScript, Tailwind y shadcn/ui

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

El charter (§7, supuestos) ya fija Next.js como frontend definitivo: multiusuario con roles, diseño adaptable a móvil
(flujos a 390 px y 1.440 px sin scroll horizontal, cámara para subir gastos) y reporte con gráficos superan lo que
Streamlit cubre bien. El prototipo `docs/cuadre-interfaz.html` define apartados, flujos y tokens de diseño.

## Decisión

- **Next.js** con App Router, **TypeScript** estricto, **Tailwind CSS v4** y **shadcn/ui** (componentes copiados al
  repositorio, no una dependencia opaca). Versiones consultadas el 2026-11-03: Next 16.4, React 19.3, Tailwind 4.3.
- **Tokens de diseño** del prototipo (variables CSS del principio del archivo) traducidos al `@theme` de Tailwind y a
  las variables que usa shadcn. El prototipo es referencia de apartados y flujos, no código a copiar.
- **Tipografías con `next/font`** (Domine y Public Sans autoalojadas). El prototipo las carga desde Google Fonts; en la
  aplicación real eso enviaría la IP de cada visitante a un tercero, algo evitable bajo el RGPD.
- **Supabase JS (`@supabase/ssr`) solo para la sesión de Auth** (registro, login, recuperación, cookies). Ninguna
  pantalla lee ni escribe tablas con `supabase-js`: los datos pasan siempre por la API FastAPI (ADR-0003 y ADR-0011).
- **El navegador llama a la API con `Authorization: Bearer <access token>`**, con CORS limitado al origen del
  frontend. El chat usa `fetch` con lectura de la respuesta SSE.
- **Protección de rutas por rol en middleware** únicamente como ayuda de experiencia de usuario. La autorización real
  está en la API y en la RLS (ADR-0005).
- **Accesibilidad y adaptación** como requisitos de cada pantalla, no de una fase final (NFR-10).

## Alternativas descartadas

- **Streamlit.** Queda solo para prototipos internos (charter §7).
- **SPA con Vite.** Sin renderizado en servidor no hay ventaja en la primera carga ni en el manejo de sesión por
  cookies, y se pierde el enrutado por carpetas.
- **Acceso directo a tablas con `supabase-js`.** Más rápido de empezar, pero reparte las reglas de negocio (numeración
  correlativa, validadores, cierre) entre cliente y servidor y rompe la generación de un cliente tipado desde OpenAPI.

## Consecuencias

- Hay dos orígenes (frontend y API): CORS, y las cookies de sesión de Supabase se leen en el servidor de Next para
  pasar el token a la API.
- El frontend no necesita nunca la service key ni la URL de la base de datos; el bundle se comprueba para ello.
- Si en algún momento la latencia del SSE a través de la plataforma de despliegue lo exige, se puede añadir un proxy
  `rewrites` hacia la API; hoy no se asume.
