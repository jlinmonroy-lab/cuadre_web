# ADR-0006 · Importes: céntimos enteros en base y API, `Decimal` en el cálculo

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

RES-02 prohíbe `float` para importes. NFR-03 exige que el 303 y el 130 coincidan al céntimo con casos resueltos a mano.
Los importes cruzan cuatro fronteras: base de datos, API, navegador y servicio de agentes. El prototipo ya trabaja en
céntimos enteros con `Math.round` por casilla.

## Decisión

- **Base de datos:** `bigint` en céntimos (`*_cents`). Los tipos de IVA y de retención son `numeric(5,2)`. Prohibido
  `real`, `double precision` y `float` en las migraciones.
- **API de cuadre-web:** enteros `*_cents` en JSON. El OpenAPI los declara `integer`; el cliente TypeScript los lee como
  `number`, seguro hasta 2^53 céntimos.
- **Cálculo (impuestos, casillas):** `Decimal` con contexto explícito, redondeo `ROUND_HALF_UP`, aplicado **una vez por
  documento y tipo de IVA** (la cuota de cada factura se redondea al céntimo antes de sumar) y una vez por casilla
  derivada (por ejemplo, el 20 % de la casilla 03 del modelo 130).
- **Contrato con agentes (C1, C2):** cadenas decimales con dos decimales (`"120.00"`): el modelo transcribe el importe tal
  como está impreso en la factura y no hace ninguna conversión, que es donde se equivocan. cuadre-web las convierte a
  céntimos en el borde y rechaza cualquier valor que no cumpla el patrón. Las herramientas MCP (C3) devuelven `*_cents` ya calculados.
- **Interfaz:** formateo con `Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })`; lectura de lo que
  teclea la persona con la función `parseCents` del prototipo (acepta `1.200,50`).
- **Guardas automáticas:** un test recorre `backend/src/cuadre/` y `supabase/migrations/` buscando `float`, `real` y
  `double precision` (sin excepciones); el generador de contratos falla si un esquema contiene `type: number`.

## Alternativas descartadas

- **`numeric(12,2)` en la base de datos.** Exacto, pero PostgREST y muchos clientes lo exponen como número JSON, y en
  Python obliga a convertir en cada borde. Con enteros no hay conversión posible que introduzca un `float`.
- **`Decimal` también en la API.** Obliga a cadenas en JSON y a parsear en TypeScript; los céntimos enteros se suman y se
  comparan sin riesgo.
- **Redondeo bancario.** La AEAT no lo prescribe y el prototipo usa medio-arriba; se mantiene.

## Consecuencias

- **La política de redondeo exacta se valida contra los cinco trimestres resueltos a mano (DEP-01, NFR-03).** Hasta
  entonces es una decisión de trabajo, no un hecho. Si la validación externa exige otro criterio, cambia aquí y en
  `cuadre.tax`, no en cada llamada.
- Las cifras agregadas que ve el chatbot ya vienen calculadas; el modelo no suma (RES-01).
