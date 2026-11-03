---
tipo: proyecto
estado: en-progreso
modulo: proyecto-final
tags: [proyectos, requisitos]
---

# Cuadre — Product Requirements Document (PRD)

---

Documento: `docs/03-prd.md`
Módulo / Asignatura: MA·S03 — De la elicitación a la especificación
Producto: Cuadre · aplicación web de facturación, contabilidad y borradores de modelos trimestrales para autónomos, con IA
Entradas: Charter de Cuadre v1.1 (`docs/00-charter.md`) · Plan de desarrollo con benchmarking y marco normativo · Prototipo de interfaz (`cuadre-interfaz.html`)
Estado: Borrador para revisión con el equipo docente · pendiente de cerrar umbrales y conflictos antes de MA·S04
Sponsor: Jorge · Fecha: 30 de octubre de 2026 · Versión: 0.2

> **Sobre los números.** Los umbrales marcados como *(propuesto)* son la propuesta inicial y se cierran con el equipo docente. Las líneas base *pendientes de medir* no existen todavía y no se inventan.

## 1. Contexto y Problema de Negocio

Un autónomo en estimación directa tiene que llevar sus ingresos y gastos al día y presentar cada trimestre el modelo 303 (IVA) y el 130 (IRPF). En la práctica, las facturas de compra se acumulan sin registrar, los datos se reconstruyen a mano al final del trimestre y surgen dudas con los clientes extranjeros: cuándo se cobra IVA, qué mención lleva la factura y en qué casilla va cada operación.

El mercado está partido en dos: software de autoservicio de 6 a 30 €/mes (Anfix, Contasimple, Holded, Quipu), que prepara los modelos pero no acompaña al usuario, y gestorías online de 15 a 65 €/mes (TaxDown, Declarando, Abaq), que los presentan con un asesor. La AEAT ofrece desde agosto de 2026 una aplicación gratuita que solo emite facturas. Cuadre ocupa el hueco: lee las facturas de compra con IA, calcula los borradores con lógica determinista, explica cada casilla y resuelve dudas citando sus fuentes. Si el autónomo trabaja con una gestoría, le da acceso a sus cuentas.

**Línea base:** el tiempo que un autónomo dedica hoy a registrar facturas y preparar su trimestre está **pendiente de medir** en las entrevistas del piloto.

## 2. Objetivos y Métricas de Éxito

| Objetivo de Negocio | Métrica (SLI / KPI) | Línea Base | Meta de Éxito (SLO) |
| --- | --- | --- | --- |
| Registrar un gasto sin esfuerzo | Precisión por campo de la lectura (NIF, fecha, base, cuota, total) | N/A (se teclea) | ≥ 90 % sobre 50 facturas |
| Trimestre fiable | Coincidencia al céntimo del 303 y el 130 con casos resueltos a mano | N/A | 100 % en ≥ 5 trimestres |
| Ahorrar tiempo | Mediana por factura registrada; tiempo hasta tener los dos borradores revisados | *Pendiente de medir* | ≤ 1 min por factura; ≤ 15 min por trimestre *(propuesto)* |
| Resolver dudas sin inventar | Respuestas correctas y citadas; preguntas fuera de alcance derivadas | N/A | ≥ 85 % y 100 % *(propuesto)* |
| Que nadie vea lo que no debe | Accesos indebidos en los tests de permisos de los tres roles | N/A | 0 |
| No olvidar un plazo | Recordatorios enviados en su fecha | N/A | 100 % en pruebas *(propuesto)* |
| Sostenibilidad económica | Coste de modelo por factura leída y por respuesta del chatbot | *Pendiente de medir* | ≤ 0,02 € y ≤ 0,01 € *(propuesto)* |

Las métricas técnicas se miden antes de la defensa; las de tiempo, en un piloto de 8 semanas con al menos 5 autónomos.

## 3. Personas y Usuarios

- **Autónomo profesional (primaria — "Lucía", diseñadora gráfica en su segundo año).** Emite de 6 a 15 facturas al mes: con retención del 7 % a empresas españolas y sin IVA a clientes de Alemania y México. Usa una hoja de cálculo y una gestoría. Necesita saber cuánto apartar y no equivocarse.
- **Gestor (secundaria — "Andrés", gestoría con unos 40 autónomos).** Cada trimestre persigue a sus clientes para que le envíen facturas. Necesita ver de un vistazo quién tiene gastos sin revisar. Es un prescriptor potencial.
- **Administrador de la plataforma.** Gestiona cuentas y la base de conocimiento del chatbot; no necesita ver datos financieros.
- **Jorge (sponsor) y equipo docente.** Jorge decide alcance y umbrales; el equipo docente valida el alcance y los casos fiscales.
- **No usuario, pero con veto: la AEAT.** Sus normas sobre facturas, modelos y VeriFactu condicionan el producto.

## 4. Alcance del Producto y User Stories Principales

La v1.0 cubre la cadena **perfil → clientes y facturas → gastos leídos con IA → cierre mensual y reporte → borradores trimestrales**, más chatbot, recordatorios y tres roles, en web para ordenador y móvil. Las historias usan **MoSCoW** y los *Must* van **por riesgo técnico decreciente**. Reparto estimado: *Must* ≈ 80 %, *Should* ≈ 15 %, *Could* ≈ 5 %. Sin un plazo cerrado, el riesgo no es dejar de llegar a una fecha, sino retrasar la primera versión que se puede usar (ver CONF-002).

### US-001 · [MUST · riesgo alto] La app lee mi factura de compra

> Como **autónomo**, quiero subir una foto o un PDF de una factura de compra y que la app rellene sus datos, para no teclearlos.

```gherkin
Scenario: Lectura de una factura con un dato ilegible
  Given un usuario autenticado
    And una foto de factura en la que el NIF del proveedor no se lee con claridad
  When el usuario sube la foto
  Then la app rellena proveedor, número, fecha, base, tipo de IVA, cuota y total
    And el NIF queda vacío y marcado como dudoso
    And el gasto no se registra hasta que el usuario confirma el dato
```

**INVEST:** pequeña porque no valida ni registra (US-005); testable con `eval_extraccion` (NFR-02).

### US-002 · [MUST · riesgo alto] El asistente no se inventa la respuesta fiscal

> Como **autónomo**, quiero preguntar una duda fiscal y recibir una respuesta con su fuente oficial o un aviso de que no puede responderla, para no decidir con información falsa.

```gherkin
Scenario: Duda que exige criterio profesional
  Given un usuario autenticado
    And una pregunta sobre su caso personal que exige un asesor
  When el usuario envía la pregunta al chatbot
  Then el chatbot no da una recomendación ni una cifra
    And explica que es una consulta para un profesional
    And ofrece contactar con su gestor, si tiene uno, o con un asesor
```

**INVEST:** es la diferencia frente a los chatbots de FAQ; testable con `eval_chatbot`, con LLM juez de un modelo distinto del evaluado (NFR-05).

### US-003 · [MUST · riesgo medio] Mi borrador del trimestre cuadra

> Como **autónomo**, quiero ver el 303 y el 130 casilla a casilla, con las facturas de cada casilla, para presentarlos con confianza.

```gherkin
Scenario: Borrador del 303 con clientes de los tres ámbitos
  Given facturas del trimestre a un cliente español, uno de la UE y uno de fuera de la UE
  When el usuario abre el borrador del 303
  Then la factura española suma en las casillas de su tipo de IVA
    And la de la UE suma en la casilla 59 y la de fuera de la UE en la 120
    And cada casilla enumera las facturas que la componen
```

**INVEST:** el riesgo es de la regla fiscal, no del modelo; testable con `test_modelo_303` y `test_modelo_130` (NFR-03).

### US-004 · [MUST · riesgo medio] Solo mi gestor ve mis cuentas, y solo si yo quiero

> Como **autónomo**, quiero invitar a mi gestor y retirarle el acceso cuando quiera, para compartir mi contabilidad sin perder el control.

```gherkin
Scenario: El gestor pierde el acceso al revocarlo
  Given un usuario que ha invitado a un gestor
  When el usuario revoca el acceso
  Then el gestor deja de verlo en su cartera
    And cualquier petición del gestor a sus datos se rechaza
    And la revocación queda en el registro de actividad
```

**INVEST:** depende de CONF-001 solo en qué puede hacer el gestor; testable con `test_rls_roles` (NFR-06).

### US-005 · [MUST · riesgo medio] La app no registra un gasto que no cuadra

> Como **autónomo**, quiero que cada factura leída se compruebe antes de registrarla, para no meter duplicados ni importes que no suman.

```gherkin
Scenario: Factura cuya suma no cuadra
  Given una factura leída con base 120,00 €, cuota 25,20 € y total 147,00 €
  When la app valida la lectura
  Then la comprobación «base más IVA igual al total» aparece como fallida
    And el botón de registrar gasto está desactivado
```

**INVEST:** reglas deterministas, sin modelo; testable con `test_validadores` y el eval adversarial (NFR-07).

### US-006 · [MUST · riesgo bajo] La factura lleva lo que tiene que llevar

> Como **autónomo**, quiero que el IVA, la retención y la mención legal se apliquen solos según el cliente, para no tener que saber la normativa.

```gherkin
Scenario: Factura a una empresa de la UE
  Given un cliente empresa de Alemania con NIF-IVA válido
  When el usuario emite una factura de 1.500,00 € a ese cliente
  Then la factura no lleva IVA ni retención e incluye «Inversión del sujeto pasivo»
    And recibe el siguiente número de su serie y ya no se puede editar
```

### US-007 · [MUST · riesgo bajo] Mi perfil rellena mis facturas

> Como **autónomo**, quiero completar una vez mis datos y los de mi negocio, para que facturas y cálculos salgan bien sin repetirlos.

```gherkin
Scenario: Perfil incompleto al emitir la primera factura
  Given un usuario sin NIF ni domicilio fiscal en su perfil
  When el usuario intenta emitir su primera factura
  Then la app lo impide y enumera por nombre los campos que faltan
```

### US-008 · [MUST · riesgo bajo] Veo cómo me ha ido el mes

> Como **autónomo**, quiero un reporte visual de cada mes cerrado, para entender cuánto he ganado, de dónde viene y cuánto debo apartar.

```gherkin
Scenario: Reporte tras el cierre automático
  Given un usuario con facturas y gastos en septiembre
  When llega el 1 de octubre
  Then septiembre queda cerrado con sus totales por cliente y por ámbito
    And su reporte muestra ingresos por cliente y ámbito, gastos por categoría, comparación con agosto y lo que conviene apartar
```

### US-009 · [MUST · riesgo bajo] No se me pasa un plazo

> Como **autónomo**, quiero un correo antes de cada plazo trimestral, para presentar a tiempo sin acordarme.

```gherkin
Scenario: Recordatorio del cuarto trimestre
  Given un usuario con recordatorios activados y 10 días de antelación
  When llega el 20 de enero
  Then recibe un correo con el plazo del 30 de enero, el importe estimado del 303 y el 130 y las facturas pendientes de revisar
```

### US-010 · [MUST · riesgo bajo] Veo mi cartera de un vistazo

> Como **gestor**, quiero ver los autónomos que me han dado acceso, con sus pendientes, para saber a quién reclamar algo.

```gherkin
Scenario: Cartera del gestor
  Given un gestor con acceso a tres usuarios, uno con cuatro facturas pendientes de revisar
  When el gestor abre su cartera
  Then ve a los tres usuarios y el que tiene pendientes aparece marcado con su número
```

### US-011 · [MUST · riesgo bajo] Uso la app desde el móvil

> Como **autónomo**, quiero subir una factura con la cámara del móvil, para registrar el gasto en el momento en que lo hago.

```gherkin
Scenario: Subida de un ticket desde el móvil
  Given un usuario autenticado en un móvil de 390 px de ancho
  When pulsa «Hacer una foto» en Gastos y fotografía un ticket
  Then la foto entra en la lectura de US-001 y ninguna pantalla necesita scroll horizontal
```

**Should have (contingencia):** facturas rectificativas; exportación de libros registro en XLSX de la AEAT; consulta de VIES en tiempo real.

**Could have:** envío del reporte mensual por correo en PDF.

**Won't have this time:** presentación ante la AEAT, VeriFactu certificado y factura electrónica B2B; conexión bancaria y cobros; app nativa y modo sin conexión; buzón de reenvío de facturas y facturas en lenguaje natural.

## 5. Requisitos del Sistema (FR & NFR)

### 5.1 Requisitos Funcionales (FR)

- **RF-001:** Registro, inicio de sesión y recuperación de contraseña, con tres roles: usuario, gestor y administrador.
- **RF-002:** Cada usuario accede solo a sus datos; cada gestor, solo a los usuarios que le han invitado; el administrador, a ningún dato financiero por defecto.
- **RF-003:** El usuario invita a un gestor y revoca su acceso cuando quiera; cada acción del gestor queda registrada.
- **RF-004:** Perfil personal y del negocio: NIF, domicilio fiscal, actividad y epígrafe, fecha de alta, régimen de IVA, retención, logo, series, IBAN y porcentaje de vivienda afecto.
- **RF-005:** Clientes: crear, editar y archivar; validar el NIF por su control; deducir el ámbito (nacional, UE o fuera de la UE).
- **RF-006:** Facturas completas con numeración correlativa por serie, IVA, retención y mención legal según el ámbito; PDF; no editables una vez emitidas.
- **RF-007:** Facturas rectificativas en serie propia *(Should)*.
- **RF-008:** Subida de facturas de compra en PDF, JPG, PNG y HEIC, desde archivo o cámara.
- **RF-009:** Extracción de los campos con un modelo multimodal, marcando los que no se leen con claridad.
- **RF-010:** Validación de NIF, fecha, cuota, suma y duplicados; el gasto no se registra hasta que todo pasa.
- **RF-011:** Gastos sin factura y clasificación por categoría.
- **RF-012:** Cierre mensual automático e idempotente el día 1, con totales por cliente y por ámbito.
- **RF-013:** Borradores del 303 y del 130 con cada casilla enlazada a sus facturas y gastos.
- **RF-014:** Reporte visual mensual: ingresos por cliente y ámbito, gastos por categoría, evolución y lo que conviene apartar.
- **RF-015:** Recordatorios por correo antes de cada plazo, con antelación configurable, y resumen de cartera para el gestor.
- **RF-016:** Chatbot sobre el uso de la app, dudas fiscales generales con cita oficial y datos del usuario con herramientas de solo lectura.
- **RF-017:** El chatbot se abstiene sin fuente o ante casos que exigen criterio profesional, y deriva al gestor o a un asesor.
- **RF-018:** Valoración de cada respuesta del chatbot (pulgar arriba o abajo, con motivo).
- **RF-019:** El administrador gestiona cuentas, roles y la base de conocimiento del chatbot.
- **RF-020:** Exportación de libros registro en XLSX de la AEAT *(Should)*.
- **RF-021:** Descarga de todos los datos y cierre de cuenta *(ver CONF-004)*.
- **RF-022:** Envío del reporte mensual por correo en PDF *(Could)*.

### 5.2 Requisitos No Funcionales (NFR) y Criterios de Evaluación (Evals)

| ID | Atributo (arc42) | Fit Criterion / Enunciado Verificable | Verificación / Eval |
| --- | --- | --- | --- |
| NFR-01 | Eficiencia / latencia | p95 ≤ 30 s por factura leída; chatbot con p95 ≤ 2 s al primer token y ≤ 8 s a la respuesta completa *(propuesto)* | Percentiles sobre la telemetría de los evals |
| NFR-02 | Idoneidad / precisión de lectura | ≥ 90 % de acierto por campo en NIF, fecha, base, cuota y total sobre 50 facturas (PDF, escaneos y fotos) | `eval_extraccion` en LangSmith |
| NFR-03 | Idoneidad / exactitud fiscal | 100 % de las casillas del 303 y el 130 coinciden al céntimo en ≥ 5 trimestres validados externamente | `test_modelo_303`, `test_modelo_130` |
| NFR-04 | Coste | ≤ 0,02 € por factura leída y ≤ 0,01 € por respuesta del chatbot *(propuesto)* | Tokens × precio, en el pipeline de evals |
| NFR-05 | *Safety* / alucinación | ≥ 85 % correctas y citadas sobre 40 preguntas; 100 % de las 10 preguntas trampa terminan en abstención y derivación *(propuesto)* | `eval_chatbot`, LLM juez distinto del evaluado y muestra revisada a mano |
| NFR-06 | Seguridad / roles | 0 accesos indebidos: usuario, gestor (también tras revocar) y administrador | `test_rls_roles` |
| NFR-07 | Seguridad / inyección | 0 facturas con instrucciones ocultas se registran sin revisión | Eval adversarial en `eval_extraccion` |
| NFR-08 | Explicabilidad | 100 % de las casillas enlazan a sus facturas y 100 % de las respuestas fiscales citan una fuente | Aserción por código |
| NFR-09 | Fiabilidad | Cierre idempotente; 100 % de recordatorios en su fecha; disponibilidad ≥ 99 % en el piloto *(propuesto)* | Tests con fechas simuladas y monitor externo |
| NFR-10 | Compatibilidad y accesibilidad | Flujos clave a 390 px y 1.440 px sin scroll horizontal en Chrome, Safari y Firefox; Lighthouse ≥ 90 *(propuesto)* | Playwright y Lighthouse en integración continua |
| NFR-11 | Privacidad / RGPD | Datos en la UE, trazas sin imágenes ni IBAN, sin uso para entrenar y contrato de encargado con cada proveedor *(propuesto — DEP-06)* | Revisión de contratos y test de sanitización |

## 6. Restricciones Técnicas y de Negocio (RES)

- **RES-01 (Técnica):** El modelo solo extrae, clasifica y redacta; los impuestos los calcula código con tests.
- **RES-02 (Técnica):** Importes en `Decimal` o céntimos enteros, nunca `float`.
- **RES-03 (Legal):** Una factura emitida no se edita ni se borra; se corrige con rectificativa *(RD 1619/2012)*.
- **RES-04 (Legal):** Nada se presenta ante la AEAT; el QR de VeriFactu se marca como simulado.
- **RES-05 (Legal):** El chatbot orienta pero no asesora, y lo dice en la interfaz.
- **RES-06 (Seguridad):** Herramientas del chatbot de solo lectura; el extractor no tiene herramientas.
- **RES-07 (Datos):** Hasta la defensa, solo datos sintéticos o facturas propias anonimizadas.
- **RES-08 (Despliegue):** 100 % online, sin instalación, con datos en la UE.

## 7. Fuera de Alcance (Exclusiones Explícitas del Sistema)

1. **No presenta modelos** ni gestiona requerimientos de Hacienda.
2. **No certifica VeriFactu** ni envía facturas electrónicas B2B.
3. **No sustituye a un asesor:** ni recomendaciones personales con efectos fiscales ni planificación fiscal.
4. **No cubre otros regímenes:** módulos, sociedades, recargo de equivalencia, IGIC, Ceuta y Melilla, forales, nóminas, alquileres con retención ni OSS.
5. **No lleva partida doble** ni genera balances.
6. **No se conecta al banco** ni cobra facturas.
7. **No es app nativa** ni funciona sin conexión.
8. **No entrena modelos:** usa modelos comerciales con prompts, salida estructurada y RAG.

## 8. Gestión de Riesgos y Mitigación

| Riesgo Identificado | Impacto | Prob. | Estrategia de Mitigación |
| --- | --- | --- | --- |
| **R-01:** El alcance retrasa la primera versión usable | Alto | Alta | Entregas incrementales por orden de riesgo; versión mínima de cada *Must* antes de pulir ninguna; servicios gestionados; revisar el alcance en cada entrega (CONF-002) |
| **R-02:** El chatbot inventa una respuesta fiscal y el usuario actúa sobre ella | Alto | Alta | RAG solo sobre fuentes oficiales con cita, abstención sin fuente, aviso visible y NFR-05 en integración continua |
| **R-03:** Una regla fiscal mal implementada da un borrador incorrecto | Alto | Media | Lógica determinista (RES-01), casos validados externamente (DEP-01), borradores marcados como orientativos |
| **R-04:** Fuga de datos entre usuarios o acceso indebido de un gestor | Alto | Media | Seguridad por fila, acceso por invitación revocable, registro de actividad y NFR-06 como puerta de despliegue |
| **R-05:** La lectura de fotos no llega al 90 % | Medio | Media | Ejemplos en el prompt, escalado a un modelo mayor y revisión humana; plan B: limitar la defensa a PDF digitales |
| **R-06:** Cambia la normativa (VeriFactu, factura electrónica) | Medio | Media | Fuera de la v1.0; modelo de datos preparado y revisión del BOE antes de la defensa (DEP-07) |

## 9. Dependencias Críticas

- **DEP-01:** Validación de 5 trimestres resueltos a mano por el equipo docente o una gestoría (NFR-03). *Jorge.*
- **DEP-02:** Decisión sobre los permisos del gestor (CONF-001); bloquea RF-002 y RF-003. *Jorge.*
- **DEP-03:** Corpus del chatbot: ayuda de la app y fuentes oficiales de la AEAT y el BOE con fecha de vigencia. *Jorge; después, el administrador.*
- **DEP-04:** Conjuntos de prueba: 50 facturas etiquetadas (2 adversariales) y 40 preguntas con respuesta de referencia (10 trampa). Va al backlog como tooling.
- **DEP-05:** Correo transaccional con dominio verificado (RF-015).
- **DEP-06:** Cuentas cloud en la UE con contrato de encargado del tratamiento (NFR-11).
- **DEP-07:** Calendario de VeriFactu: vigente el 1 de julio de 2027 para autónomos, con un aplazamiento a 2028 anunciado y sin norma publicada.

## 10. Supuestos

| # | Supuesto | Si fuera falso |
| --- | --- | --- |
| SUP-01 | El usuario es autónomo profesional en estimación directa, régimen general de IVA y territorio común | Hay que soportar otros regímenes antes de lanzar |
| SUP-02 | Acepta subir facturas a una app online si la seguridad es visible | Hace falta un argumento de confianza más fuerte antes del piloto |
| SUP-03 | La mayoría de facturas son PDF digitales o fotos legibles | NFR-02 no se alcanza y se aplica el plan B de R-05 |
| SUP-04 | Las fuentes de la AEAT y el BOE cubren las dudas frecuentes | El chatbot se abstiene demasiado y US-002 pierde valor |
| SUP-05 | Los servicios gestionados evitan construir autenticación, permisos y correo | Los roles y recordatorios alargan el desarrollo y retrasan el piloto |
| SUP-06 | El gestor trabaja sobre la cuenta del usuario, sin contabilidad propia | Hace falta un modelo de datos de despacho |
| SUP-07 | Next.js cubre multiusuario, diseño adaptable y gráficos sin un aprendizaje excesivo | El reporte y el diseño adaptable se simplifican |

## 11. Registro de Conflictos

Cada conflicto tiene una propuesta escrita en los requisitos, pero sigue **abierto** hasta que decida su responsable.

| ID | Conflicto (parte A vs. parte B) | Opciones | Propuesta | Decide | Estado |
| --- | --- | --- | --- | --- | --- |
| CONF-001 | **Gestor:** emitir facturas y registrar gastos por sus clientes · **Autónomo:** que nada entre en sus cuentas sin saberlo | (a) solo consulta, revisa y descarga; (b) también escribe, con registro y aviso; (c) permisos configurables | (a), escrita en RF-003 y US-010 | Jorge (DEP-02) | Abierto · bloquea RF-002 y RF-003 |
| CONF-002 | **Sponsor:** todas las funciones como *Must* · **Piloto:** tener cuanto antes una versión usable con autónomos reales | (a) entregar por fases, empezando por el núcleo contable; (b) bajar a *Should* el panel del gestor y la parte visual del reporte; (c) no lanzar el piloto hasta tener todo | (a), mitigación de R-01 | Jorge con el equipo docente | Abierto |
| CONF-003 | **Autónomo:** respuestas concretas a su caso · **Responsabilidad legal:** no dar asesoramiento | (a) norma general citada y derivación de lo personal; (b) casos personales con aviso; (c) no responder nada fiscal | (a), escrita en US-002 y RF-017 | Jorge, con asesoría legal si hay piloto | Abierto |
| CONF-004 | **RGPD:** derecho de supresión · **Normativa fiscal:** conservar facturas al menos 4 años | (a) exportación completa y borrado; (b) bloqueo durante el plazo legal y borrado después; (c) cuenta en solo lectura hasta el fin del plazo | Pendiente | Jorge, con asesoría legal (DEP-06) | Abierto · no bloquea la defensa (RES-07) |

## 12. Matriz de Trazabilidad

Para los *Must* y lo que toca al modelo, a los permisos o a la ley. El criterio de aceptación de cada fila es el escenario de su historia; la columna Spec enlaza con el desarrollo guiado por specs de MA·S04.

| ID | Fuente | Historia | Test / eval | Spec | Estado |
| --- | --- | --- | --- | --- | --- |
| RF-009 | Charter §4 (Gastos) | US-001 | `eval_extraccion` (NFR-01, NFR-02) | SPEC-004 | Especificado |
| RF-016, RF-017 | Charter §4 (Chatbot) y §6 | US-002 | `eval_chatbot` (NFR-05, NFR-08) | Por escribir | Propuesto · DEP-03 |
| RF-013 | Charter §4 (Trimestres) | US-003 | `test_modelo_303`, `test_modelo_130` (NFR-03) | SPEC-007, SPEC-008 | Especificado · DEP-01 |
| RF-002, RF-003 | Charter §4 (Roles) | US-004 | `test_rls_roles` (NFR-06) | Por escribir | Bloqueado por CONF-001 |
| RF-010 | Plan de desarrollo | US-005 | `test_validadores`, eval adversarial (NFR-07) | SPEC-005 | Especificado |
| RF-006 | RD 1619/2012 · charter §4 | US-006 | `test_emision_factura` | SPEC-001, SPEC-003 | Especificado |
| RF-004 | Charter §4 (Perfil) | US-007 | `test_perfil_obligatorio` | Por escribir | Propuesto |
| RF-012, RF-014 | Charter §4 (Mensual y reporte) | US-008 | `test_cierre_mensual` (NFR-09) | SPEC-006 | Propuesto · falta la parte visual |
| RF-015 | Charter §4 (Recordatorios) | US-009 | `test_recordatorios` (NFR-09) | Por escribir | Propuesto · DEP-05 |
| RF-003 | Charter §4 (Gestor) | US-010 | `test_cartera_gestor` | Por escribir | Bloqueado por CONF-001 |
| RF-008 | Charter §4 (Diseño adaptable) | US-011 | `e2e_movil` (NFR-10) | Por escribir | Propuesto |
| RF-021 | RGPD · RES-03 | *(pendiente)* | `test_exportacion_datos` | Por escribir | Depende de CONF-004 |
