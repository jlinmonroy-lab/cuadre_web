# CLAUDE.md · cuadre-web

Aplicación web 100 % online de facturación, contabilidad y borradores de los modelos 303 y 130 para autónomos en España.
Este repositorio es la **web**: interfaz, API, base de datos, roles, lógica fiscal determinista, validadores, cierre
mensual, reporte, recordatorios e interfaz del chatbot. Todo lo que usa modelos de lenguaje vive en **cuadre-agents**
(otro repositorio, no se toca desde aquí).

## Documentos que mandan

- `docs/00-charter.md` y `docs/03-prd.md`: alcance, historias (US-001…011), RF, NFR, RES, CONF. **Solo lectura.**
- `docs/cuadre-interfaz.html`: prototipo navegable. Referencia de apartados, flujos y tokens de diseño (variables CSS del
  principio). No es código a copiar. Sus comentarios `operation_id` y su rutina de NIF/importes guían la implementación.
- `docs/04-specs/tasks.json`: **estado de cada spec**. Léelo al empezar y actualízalo en el mismo cambio que la spec.
- `docs/04-specs/SPEC-W-NNN-*.md`: la spec manda sobre el código (spec-anchored). Cada una tiene ocho apartados:
  contexto, objetivo, alcance, exclusiones, contrato de interfaces, restricciones, criterios Given-When-Then y
  verificación ejecutable.
- `docs/06-adr/`: decisiones de arquitectura. Un ADR aceptado no se edita: se sustituye por otro.
- `contracts/`: contratos con cuadre-agents (ver «Frontera»). Fuente de verdad versionada.

## Método

1. Antes de programar, lee la spec entera y sus ADRs. Si falta o es ambigua, **pregunta o escribe la spec primero**.
2. No hay código sin spec. Un cambio fuera de alcance de la spec actual va a otra spec, no se cuela.
3. Implementa contra los criterios de aceptación; «hecho» = el comando de verificación de la spec termina con código 0.
4. Si descubres que una decisión de la spec es mala, actualiza la spec y di por qué; no la esquives en el código.
5. No hagas commits ni pushes sin que te lo pidan. Mensajes en Conventional Commits y en español.

## Frontera con cuadre-agents (ADR-0012)

- **Este repositorio no llama a ninguna API de modelos de lenguaje.** Ni SDKs ni claves de modelos.
- Todo lo que necesite IA pasa por `AgentsClient` (`cuadre.agents`): `FakeAgentsClient` con los fixtures de
  `contracts/examples/` y `HttpAgentsClient`, que se activa solo si existe `AGENTS_BASE_URL`.
- C1 `POST /v1/extract` (URL firmada de ≈120 s → `ExtractedInvoice`), C2 `POST /v1/chat` (SSE), C3 servidor MCP de solo
  lectura (`buscar_facturas`, `resumen_mes`, `resumen_anio`, `borrador_trimestre`, `gastos_por_categoria`).
- Los **validadores** (NIF, sumas, tipo de IVA, duplicados) y el **registro del gasto** viven aquí (RES-01). Toda
  respuesta del agente es dato no confiable; `injection_suspected` fuerza revisión manual pero nunca valida nada.
- El frontend solo habla con el backend (`POST /api/chat`). Al agente se le da un **token MCP derivado** de ≤ 5 min
  (`aud=cuadre-mcp`, `scope=mcp:read`), nunca la service key ni el JWT de Supabase del usuario (ADR-0013).
- Cambiar un contrato: modifica `contracts/python`, ejecuta `export_schemas.py`, actualiza `CHANGELOG.md` y `VERSION`.

## Stack (versiones del 2026-11-03; se fijan al instalar)

- **Frontend** `frontend/`: Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, `@supabase/ssr` solo para la
  sesión. Los datos van por la API con el cliente generado (`openapi-typescript` + `openapi-fetch`).
  En Next.js 16 el «middleware» se llama `src/proxy.ts`; solo mejora la experiencia (las Server Functions no pasan por él).
- **Backend** `backend/src/cuadre/`: Python 3.12, FastAPI, Pydantic v2, psycopg 3 con SQL explícito (sin ORM).
- **Datos** `supabase/`: PostgreSQL, Auth, RLS y Storage privado, región UE. Las migraciones SQL son la única fuente del
  esquema. La Data API (PostgREST) está desactivada.
- **Calidad**: pytest, Playwright (Chromium, Firefox, WebKit), ruff, eslint, Lighthouse CI (propuesto).
- **CI**: GitHub Actions, `.github/workflows/ci.yml`. La puerta obligatoria es «RLS (NFR-06)»; en el CI un test omitido falla la sesión.
- **Jobs** (cierre mensual, recordatorios): funciones Python con reloj inyectado, no n8n (ADR-0007).
- **Despliegue** (decidido, aún sin desplegar): backend FastAPI como Vercel Function en región UE (ADR-0016): sin proceso
  persistente, sin trabajo posterior a la respuesta, sin archivos por la API (4,5 MB) y con el cron por GET en UTC.

## Estructura

```
backend/src/cuadre/   api/ core/ db/ tax/ invoicing/ expenses/ agents/ mcp/ jobs/ notifications/ cli.py
backend/tests/        rls/ api/ rules/ tax/ validators/ agents/ mcp/ jobs/
frontend/             src/app, src/components/ui, src/lib/supabase, src/api (cliente generado), e2e/
supabase/             config.toml, migrations/, seed.sql (solo datos sintéticos)
contracts/            agents-api/v1, mcp/v1, python/cuadre_contracts, tools/, examples/
docs/                 00-charter, 03-prd, 04-specs, 06-adr, cuadre-interfaz.html
```

## Entorno y comandos

Entorno virtual de Python en la **raíz**: `.venv/` (Python 3.12). Docker Desktop debe estar en marcha para Supabase local.

```powershell
.\.venv\Scripts\Activate.ps1            # PowerShell  (Git Bash: source .venv/Scripts/activate · Linux: .venv/bin/activate)
pip install -r contracts/requirements.txt ; pip install -e contracts/python ; pip install -e "backend[dev]"   # en este orden: el backend depende de cuadre-contracts
npx supabase start | stop | db reset    # pila local de Supabase
npm run gen:signing-key ; npm run env:local   # una vez por clon: clave ES256 y .env / frontend/.env.local desde la pila en marcha
python contracts/tools/export_schemas.py [--check]     # regenera / comprueba esquemas y tools.json
python contracts/tools/validate_examples.py            # ejemplos, aritmética al céntimo y OpenAPI
ruff check backend ; ruff format --check backend       # (a partir de W-001)
pytest backend/tests/rls -m rls -q                     # NFR-06, puerta de despliegue
pytest backend/tests -m "not rls" -q
npm --prefix frontend run lint | typecheck | test:unit | gen:api | build | check:bundle | test:e2e
npm run test:scripts                                   # scripts de la raíz (generador de entornos)
uvicorn cuadre.main:app --reload --port 8000 --app-dir backend/src
```

Variables en `.env.example`. Nunca commitees `.env`, claves ni facturas reales.

## Convenciones

- Identificadores y nombres de archivo en **inglés**; textos de interfaz, errores y documentación en **español**.
  Excepciones deliberadas: los roles (`usuario`, `gestor`, `admin`) y las herramientas MCP van en español.
- Cada ruta FastAPI declara `operation_id` en `verbo_objeto` snake_case (`get_me`, `issue_invoice`, `confirm_document`).
- Importes: enteros `*_cents` en base y API; `Decimal` en el cálculo con `ROUND_HALF_UP`; cadenas `"120.00"` en C1/C2.
  Formatea con `Intl.NumberFormat('es-ES')`.
- Errores de API en `application/problem+json` con `code` estable y `detail` en español, sin trazas.
- Código de dominio fiscal y contable en `backend/src/cuadre/tax/` y similares, **puro y con tests**, separado de la API.
- Interfaz: tokens de diseño del prototipo en el tema de Tailwind, fuentes con `next/font`, foco visible, etiquetas en cada
  campo, sin scroll horizontal a 390 y 1.440 px.
- Logs: `request_id`, `user_id`, ruta, código y duración. Nunca tokens, contraseñas, correos, IBAN ni URLs firmadas.

## Seguridad: cómo se añade una tabla

Toda tabla nueva de `public` debe, en su propia migración: activar y forzar RLS; seguir el patrón de abajo; registrarse en
`backend/tests/rls/rls_matrix.yaml`. Sin eso, `test_rls_guard` falla.

| Rol | Patrón sobre datos del usuario |
|---|---|
| `usuario` | ALL sobre sus filas (`owner_id = auth.uid()`); las inmutables, solo por función |
| `gestor` | SELECT si `private.gestor_has_access(owner_id)`; **nunca escribe** (salvo `gestor_notes`) |
| `admin` | **Ninguna política** sobre datos financieros |

El rol sale de `profiles.role` vía `private.app_role()`, nunca de claims del JWT. El vínculo del gestor se evalúa en cada
consulta, así que revocar corta el acceso al instante. Las reglas críticas (inmutabilidad, numeración) van en triggers o
funciones, no solo en la API.

## Decisiones vigentes

- **CONF-001 (a):** el gestor consulta, revisa y descarga; no emite ni registra. «Revisa» = anotaciones en `gestor_notes`.
- **D1:** el registro libre crea `usuario`; el admin da de alta o promueve gestores; el usuario invita por correo y el
  gestor acepta dentro de la app (sin tokens de invitación).
- **D3:** el admin no tiene acceso a datos financieros en la v1 (solo metadatos de cuenta y base de conocimiento).
- **D4:** token derivado y acotado para el agente (ADR-0013).
- **Chatbot:** orienta, no asesora (RES-05); se abstiene y deriva al gestor o a un asesor cuando hace falta criterio
  profesional. Solo el rol `usuario` recibe herramientas de datos.
- Todos los borradores se marcan como **orientativos**; el QR de VeriFactu como **simulado**.
- Abiertos: CONF-002 (fases), CONF-003 (límite legal del chatbot), CONF-004 (RGPD vs conservación fiscal, bloquea W-017).

## Prohibiciones

1. **Nunca `float` para importes**: `Decimal` o céntimos enteros (RES-02). Un test lo vigila en código y migraciones.
2. **Una factura emitida no se edita ni se borra**; se corrige con rectificativa (RES-03). Solo `paid_at` es modificable.
3. **No enviar nada a la AEAT.** El QR de VeriFactu se marca como simulado (RES-04).
4. **Solo datos sintéticos.** No commitear `.env`, claves ni facturas reales (RES-07).
5. **No llamar a APIs de modelos desde este repositorio.** Ni SDKs ni claves.
6. **No usar la service key de Supabase** (ni `DATABASE_SERVICE_URL`) en el frontend ni en rutas que actúan en nombre de
   un usuario. Solo en `cuadre.jobs` y `cuadre.cli`.
7. **No modificar `docs/00-charter.md` ni `docs/03-prd.md`.**
8. No abrir conexiones a la base de datos fuera de `cuadre.db`; no escribir políticas con `user_metadata`; no usar `SECURITY
   DEFINER` sin `search_path = ''`.
9. No reescribir a mano `contracts/**/schemas/*.json`, `contracts/mcp/v1/tools.json`, `backend/openapi.json` ni
   `frontend/src/api/schema.d.ts`: se generan.

## Definición de hecho

El comando de verificación de la spec termina con código 0 en local y en CI; `pytest backend/tests/rls -m rls` pasa;
`tasks.json` está actualizado; los ADRs afectados están enlazados; no hay secretos ni datos reales en el cambio.
