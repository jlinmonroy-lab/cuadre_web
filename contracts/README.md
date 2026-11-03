# contracts/ · contratos entre cuadre-web y cuadre-agents

**Versión vigente: 1.0.0** (`VERSION`, `CHANGELOG.md`). Esta carpeta es la fuente de verdad: cuadre-agents la copia
tal cual (o la consume como paquete) y cuadre-web la cumple. Si hay que cambiar algo, se cambia aquí primero.

## Qué hay

| Contrato | Qué es | Dónde |
|---|---|---|
| **C1 · Lectura de facturas** | `POST {AGENTS_BASE_URL}/v1/extract`: URL firmada → `ExtractedInvoice` | `agents-api/v1/openapi.yaml`, `schemas/extract_*.json`, `schemas/extracted_invoice.schema.json` |
| **C2 · Chatbot** | `POST {AGENTS_BASE_URL}/v1/chat`: historial → respuesta SSE | `agents-api/v1/openapi.yaml`, `schemas/chat_*.json` |
| **C3 · Herramientas de datos** | Servidor MCP de solo lectura que expone cuadre-web | `mcp/v1/tools.json`, `mcp/v1/README.md` |

Además: `python/cuadre_contracts/` (modelos Pydantic de los que se **derivan** los esquemas), `tools/` (generador y
validador), `examples/` (casos sintéticos).

## Reglas

1. **El modelo Pydantic manda.** `schemas/*.json` y `mcp/v1/tools.json` se generan con
   `python contracts/tools/export_schemas.py`. No se editan a mano. El CI ejecuta `--check` y falla si difieren.
2. **Los ejemplos son tests.** `python contracts/tools/validate_examples.py` valida cada ejemplo contra su esquema
   JSON y su modelo Pydantic, y comprueba que las cifras cuadran al céntimo.
3. **Sin `float`** (RES-02). Los importes viajan como cadenas decimales (`"120.00"`) en C1 y C2, y como céntimos
   enteros (`*_cents`) en C3. El generador falla si un esquema contiene `type: number`.
4. **Compatibilidad.** En 1.x solo se añaden campos opcionales y los receptores ignoran los que no conocen. Un cambio
   incompatible crea `v2/` y se acuerda con cuadre-agents antes de fusionarse. La web envía
   `X-Cuadre-Contract-Version: 1`.
5. **Idioma.** Los identificadores de C1 y C2 están en inglés; los roles (`usuario`, `gestor`) conservan el
   vocabulario de dominio de la base de datos; las herramientas MCP van en español a propósito, porque las lee un
   modelo que conversa con el usuario en español.

## Frontera de responsabilidades (ADR-0012)

| cuadre-web (este repo) | cuadre-agents |
|---|---|
| Sube el archivo a Storage y genera la URL firmada | Descarga, lee y devuelve `ExtractedInvoice` |
| Valida NIF, sumas, tipo de IVA y duplicados; registra el gasto (RES-01) | No valida ni registra nada |
| Trata toda extracción como dato no confiable y fuerza revisión si `injection_suspected` | Marca `injection_suspected` y `doubtful_fields` |
| Guarda el historial, asigna `message_id`, persiste la valoración | Genera la respuesta, las citas y la abstención |
| Emite el token MCP derivado (≤ 5 min) y sirve el MCP de solo lectura | Reenvía ese token al MCP; nunca recibe la service key |
| Calcula impuestos y casillas con código y tests | Explica las cifras que le dan las herramientas; no las recalcula |

## Cómo se usa

```powershell
# Con el entorno virtual de la raíz activado (.\.venv\Scripts\Activate.ps1)
python contracts/tools/export_schemas.py            # regenera esquemas y tools.json
python contracts/tools/export_schemas.py --check    # CI: falla si hay deriva
python contracts/tools/validate_examples.py         # CI: ejemplos, aritmética y OpenAPI
```

**Para cuadre-agents:** copia `contracts/` (o instala `contracts/python` como paquete `cuadre-contracts`), implementa
`agents-api/v1/openapi.yaml` y usa `examples/` como casos de partida de sus evals. Sus specs usan el prefijo
`SPEC-A-NNN`; las de este repositorio, `SPEC-W-NNN`.
