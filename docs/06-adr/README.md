# Registro de decisiones de arquitectura (ADR)

Un ADR por decisión de stack y uno para la frontera entre repositorios. Formato breve: contexto, decisión, alternativas
descartadas, consecuencias. Un ADR aceptado no se edita: se sustituye por otro que lo enlaza.

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-monorepo.md) | Monorepo `frontend/` + `backend/` + `supabase/` + `contracts/` | Aceptado |
| [0002](0002-frontend-nextjs.md) | Frontend: Next.js (App Router), TypeScript, Tailwind y shadcn/ui | Aceptado |
| [0003](0003-backend-fastapi-sql-directo.md) | Backend: FastAPI + Pydantic v2, Postgres por SQL directo con la identidad del usuario | Aceptado |
| [0004](0004-supabase-ue.md) | Supabase en la UE: Postgres, Auth, RLS y Storage privado | Aceptado |
| [0005](0005-autenticacion-roles-rls.md) | Autenticación, roles y autorización | Aceptado |
| [0006](0006-importes-en-centimos.md) | Importes: céntimos enteros en base y API, `Decimal` en el cálculo | Aceptado |
| [0007](0007-jobs-programados.md) | Jobs programados en código Python, no en n8n | Aceptado |
| [0008](0008-correo-transaccional.md) | Correo transaccional detrás de una interfaz | Propuesto |
| [0009](0009-entorno-de-desarrollo.md) | Entorno de desarrollo: venv en la raíz, npm y Supabase local | Aceptado |
| [0010](0010-calidad-tests-ci.md) | Calidad: pytest, Playwright, ruff, eslint y CI con puertas | Aceptado |
| [0011](0011-cliente-typescript-generado.md) | Cliente TypeScript generado desde `openapi.json` | Aceptado |
| [0012](0012-frontera-web-agentes.md) | Frontera entre cuadre-web y cuadre-agents | Aceptado |
| [0013](0013-mcp-solo-lectura-token-derivado.md) | Servidor MCP de solo lectura con token derivado y acotado | Aceptado |
| [0014](0014-despliegue-ue.md) | Despliegue 100 % en la UE | Propuesto |
