# Contrato 3 · Servidor MCP de solo lectura (v1)

cuadre-web expone herramientas de consulta sobre los datos **del propio usuario** para que el agente del chatbot
responda preguntas como «¿cuánto he facturado a clientes de la UE este año?». Este archivo describe el servidor;
`tools.json` (generado) define cada herramienta con su esquema de entrada y de salida.

## Transporte y autenticación

- **Transporte:** MCP sobre HTTP en streaming, montado en el propio backend FastAPI en `/mcp`.
- **Credencial:** `Authorization: Bearer <token MCP>`. No es el JWT de Supabase del usuario (decisión D4, ADR-0013).
  Lo emite el backend por cada petición de chat y solo sirve para este servidor:

  | Claim | Valor |
  |---|---|
  | `iss` | `cuadre-web` |
  | `aud` | `cuadre-mcp` |
  | `scope` | `mcp:read` |
  | `sub` | id del usuario |
  | `conv` | `conversation_id` del chat |
  | `exp` | emisión + 5 min como máximo |

- **RLS.** Con un token válido, el servidor abre una transacción `READ ONLY`, hace `SET LOCAL ROLE authenticated` y
  fija las claims del usuario. Las políticas de seguridad por fila se aplican igual que en la API: el agente no puede
  ver nada que el usuario no vea. Un gestor o un administrador no reciben herramientas de datos (`mcp_url` = `null`).
- **Sin service key.** El servidor MCP nunca usa la clave de servicio de Supabase.

## Reglas de las herramientas

1. **Solo lectura.** Ninguna herramienta escribe. Las anotaciones MCP son `readOnlyHint: true`.
2. **Cifras ya calculadas.** Todas devuelven totales y resultados agregados por el servidor para que el modelo
   no sume ni calcule impuestos (RES-01). Las descripciones se lo piden expresamente.
3. **Céntimos enteros** (`*_cents`), moneda `EUR`. Nada de `float` (RES-02).
4. **Sin datos sensibles de terceros:** nunca IBAN, domicilios ni NIF de clientes o proveedores.
5. **Orientativo.** `borrador_trimestre` siempre devuelve `orientativo: true` y un aviso: es un borrador, no se
   presenta ante la AEAT.
6. **Marca temporal.** Toda salida lleva `as_of` (UTC) para que el modelo pueda decir «a fecha de…».
7. **Límites.** `buscar_facturas` devuelve como máximo 50 filas, pero sus totales cubren **todas** las coincidencias
   (`truncado` avisa). Las fechas se interpretan en `Europe/Madrid`.

## Errores

Un fallo se devuelve como resultado MCP con `isError: true` y un contenido conforme a `errorSchema` de `tools.json`:

| `code` | Cuándo |
|---|---|
| `invalid_params` | Parámetros fuera de rango o incompatibles (por ejemplo `mes` y `trimestre` a la vez) |
| `no_data` | No hay datos para el periodo pedido |
| `unauthorized` | Token ausente, caducado, con audiencia o alcance incorrectos |
| `internal` | Error interno; el mensaje no filtra detalles |

## Herramientas (v1)

| Herramienta | Responde a |
|---|---|
| `buscar_facturas` | «¿Qué facturas tengo a clientes de la UE?», «¿cuáles me faltan por cobrar?» |
| `resumen_mes` | «¿Cómo me fue en septiembre?» |
| `resumen_anio` | «¿Cuánto he facturado a clientes de la UE este año?» (añadida respecto al borrador del enunciado) |
| `borrador_trimestre` | «¿Qué sale en el 303 de este trimestre y por qué?» |
| `gastos_por_categoria` | «¿En qué se me va el dinero?» |

Ejemplos de entrada y salida de cada una: `../../examples/mcp/`.
