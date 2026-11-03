---
tipo: proyecto
estado: en-progreso
modulo: proyecto-final
tags: [proyectos]
---

# Project Charter — Cuadre

Sponsor: Jorge - Autor del proyecto y product owner
Stakeholders identificados:
- **Jorge** - Sponsor, product owner y desarrollador; decide el alcance y las prioridades
- **Equipo docente de Neoland** - Evalúa el proyecto final; valida el alcance y los casos fiscales de prueba
- **Autónomo profesional** - Usuario primario; factura pocos servicios al mes, con clientes en España, en la UE y fuera de ella, y sin conocimientos contables
- **Administrador de la plataforma** - Usuario secundario; da de alta y de baja cuentas, atiende incidencias y mantiene la base de conocimiento del chatbot
- **Gestorías y asesores fiscales** - Usuarios secundarios con el rol de gestor: llevan las cuentas de varios autónomos desde la aplicación. También son afectados, porque parte de su trabajo trimestral se automatiza, y siguen siendo el destino de las dudas que el chatbot no debe resolver
- **AEAT y legislador** - Actor externo con poder de veto: VeriFactu, el contenido obligatorio de las facturas y los modelos fiscales condicionan el producto
- **Proveedores cloud (modelo de IA, base de datos, alojamiento, correo)** - Dependencia de coste, disponibilidad y cumplimiento del RGPD, al ser una aplicación 100 % online

Fecha: 28-10-2026 ·
Versión: 1.1 (añade el rol de gestor y pasa el chatbot, los recordatorios y el reporte mensual a Must)

## 1. Problema
Un autónomo en estimación directa tiene que llevar sus ingresos y gastos al día y presentar cada trimestre el modelo 303 (IVA) y el 130 (IRPF). En la práctica, las facturas de compra se acumulan en papel o en PDF sin registrar, los datos se reconstruyen a mano en una hoja de cálculo al final de cada trimestre, y surgen dudas con los clientes extranjeros (cuándo se cobra IVA, qué mención lleva la factura y en qué casilla va cada operación).

Las soluciones actuales obligan a elegir entre software barato, de 6 a 30 €/mes, que prepara los modelos pero no acompaña al usuario, y gestorías online, de 15 a 65 €/mes, que sí lo hacen pero cuestan más. La aplicación gratuita de la AEAT solo emite facturas. Los chatbots fiscales del mercado responden preguntas generales, pero no conocen los datos del usuario ni actúan sobre ellos.

## 2. Objetivo
Que un autónomo lleve **toda su contabilidad en una sola aplicación web**, desde el ordenador o el móvil, y tenga **preparados sin esfuerzo los borradores del 303 y del 130** cada trimestre. La aplicación lee sus facturas de compra con IA, le avisa por correo antes de cada plazo, le resume cada mes cómo va su negocio y le resuelve las dudas sobre la aplicación y sobre fiscalidad con un asistente que cita sus fuentes. Si trabaja con una gestoría, le da acceso a sus cuentas en lugar de enviarle papeles cada trimestre.

## 3. Alcance — fuera
### Relación con la Agencia Tributaria
- **Presentación de modelos:** la aplicación prepara los borradores, pero no presenta nada ante la AEAT. El usuario los presenta él mismo o a través de su gestoría.
- **Certificación VeriFactu y factura electrónica B2B:** en esta versión, el código QR y los registros de facturación son simulados y se marcan como no remitidos. No se certifica el software ni se envían facturas en formato electrónico estructurado.
- **Requerimientos y notificaciones de Hacienda:** la aplicación no los gestiona ni los responde.

### Asesoramiento profesional
- **El chatbot orienta, no asesora:** explica conceptos y normas con fuentes oficiales y responde con los datos del propio usuario, pero no sustituye a un asesor fiscal. No recomienda decisiones personales con efectos fiscales (cambiar de régimen, darse de alta en el ROI, deducir un gasto dudoso) ni hace planificación fiscal; en esos casos deriva a un profesional.
- **Validación legal de cada operación:** la aplicación aplica reglas generales; los casos especiales quedan bajo la responsabilidad del usuario.

### Regímenes y operaciones no cubiertos
- Estimación objetiva (módulos, modelo 131), sociedades (Impuesto sobre Sociedades) y recargo de equivalencia.
- Canarias (IGIC), Ceuta y Melilla, y territorios forales (País Vasco y Navarra).
- Trabajadores a cargo y alquileres con retención (modelos 111 de nóminas y 115), ventas a particulares de la UE por ventanilla única (OSS) y contabilidad completa por partida doble (balances).

### Integraciones y plataformas
- **Banca y cobros:** sin conexión bancaria (PSD2) ni pasarelas de pago.
- **Aplicaciones nativas:** no hay app de iOS ni de Android; la versión móvil es la propia web adaptada. Tampoco funciona sin conexión.

### Datos
- **Datos reales durante el bootcamp:** hasta la defensa se trabaja solo con datos sintéticos o facturas propias anonimizadas.

## 4. Alcance — dentro
El alcance se prioriza con MoSCoW. Lo marcado como *Must* entra en la defensa del proyecto final (cuatro semanas); lo marcado como *Could* entra solo si sobra tiempo tras cumplir todas las puertas de control, y si no, queda para la fase posterior al bootcamp.

### Núcleo contable (definido en el plan de desarrollo)
| Función | Qué incluye | Prioridad |
| --- | --- | --- |
| **Clientes** | Ficha con NIF o NIF-IVA, país y ámbito (nacional, UE o extracomunitario); validación del NIF y consulta en VIES | Must |
| **Facturas** | Emisión con numeración por serie, IVA, retención de IRPF y mención legal automática según el ámbito del cliente; PDF; estado de cobro | Must |
| **Gastos** | Subida de facturas de compra desde archivo o con la cámara; lectura con IA, validación de NIF, sumas y duplicados, y revisión de los datos dudosos; gastos sin factura (cuota de autónomos) | Must |
| **Contabilidad mensual** | Cierre automático el día 1 con ingresos por cliente, total del mes, acumulado del año y desglose nacional, UE y fuera de la UE | Must |
| **Trimestres** | Borradores del 303 y del 130 casilla a casilla, enlazados a las facturas que los componen | Must |

### Funciones nuevas
| Función | Qué incluye | Prioridad |
| --- | --- | --- |
| **Aplicación 100 % online** | Desplegada en la nube y accesible desde el navegador, sin instalación; datos y archivos en una base de datos y un almacenamiento gestionados | Must |
| **Multiusuario con roles** | Registro e inicio de sesión; cada usuario ve solo sus datos o los que se le han compartido. Tres roles:<br>**Usuario**: el autónomo; gestiona su negocio y decide qué gestor puede acceder a sus cuentas.<br>**Gestor**: lleva las cuentas de varios usuarios desde un panel con su cartera de clientes; solo accede a los usuarios que le han invitado, y el usuario puede retirarle el acceso en cualquier momento. Revisa gastos, consulta la contabilidad y los trimestres y descarga los libros registro; cada acción suya queda registrada.<br>**Administrador**: gestiona la plataforma (cuentas, roles y base de conocimiento del chatbot), sin acceso por defecto a los datos financieros de los usuarios | Must |
| **Perfil personal y del negocio** | Datos personales y fiscales (NIF, domicilio fiscal, actividad y epígrafe, fecha de alta, régimen de IVA), retención aplicable (15 % o 7 % en los tres primeros años), logo, series de facturación, IBAN para las facturas y porcentaje de la vivienda afecto a la actividad. Alimenta las facturas y las reglas fiscales | Must |
| **Diseño adaptable** | Todos los flujos funcionan en ordenador, tableta y móvil, sin scroll horizontal; la subida de gastos aprovecha la cámara del móvil | Must |
| **Chatbot** | Responde tres tipos de pregunta: cómo se usa la aplicación (ayuda de la app), dudas económicas y fiscales generales (fuentes oficiales de la AEAT y el BOE, con la cita de cada respuesta) y preguntas sobre los datos del usuario («¿cuánto he facturado a clientes de la UE este año?») mediante herramientas MCP de solo lectura. Lo que excede su alcance lo deriva a un asesor, o al gestor del usuario si tiene uno | Must |
| **Recordatorios por correo** | Aviso antes de cada plazo trimestral con el borrador del 303 y del 130 y la lista de facturas pendientes de revisar; el usuario elige la antelación o desactiva los avisos. El gestor recibe un resumen con los plazos de toda su cartera | Must |
| **Reporte mensual visual** | Resumen financiero de cada mes en la app, con gráficos: ingresos por cliente y por ámbito, gastos por categoría, evolución frente a meses anteriores y lo que conviene apartar para impuestos | Must |
| **Envío del reporte por correo en PDF** | El reporte mensual se envía al usuario, y a su gestor si lo tiene, como PDF adjunto | Could |

## 5. Criterios de éxito

> Los umbrales marcados como *(propuesto)* todavía no están validados con el equipo docente: son la propuesta inicial y se cierran en la revisión del alcance. Las métricas técnicas se miden antes de la defensa; las de uso, en un piloto posterior con autónomos reales.

| Métrica | Valor objetivo | Plazo | Cómo se mide |
| --- | --- | --- | --- |
| Precisión de la lectura de facturas | ≥ **90 %** de acierto por campo (NIF, fecha, base, cuota y total) sobre un golden set de 50 facturas | Semana 2 | Eval por campo registrado en LangSmith |
| Exactitud de los cálculos fiscales | **100 %** de coincidencia, al céntimo, en el 303 y el 130 de al menos 5 trimestres resueltos a mano | Semana 3 | Tests automáticos (`pytest`) |
| Calidad del chatbot | ≥ **85 %** de respuestas correctas y con fuente citada sobre 40 preguntas de prueba (app, fiscalidad y datos propios), y el **100 %** de las preguntas fuera de alcance derivadas a un profesional *(propuesto)* | Semana 4 | Eval con respuestas de referencia y preguntas trampa |
| Aislamiento de datos | **0** accesos a datos ajenos y **100 %** de los tests de permisos superados en los tres roles: el usuario solo ve lo suyo, el gestor solo ve a los usuarios que le han invitado (y pierde el acceso al revocarlo) y el administrador no ve datos financieros | Semana 4 | Tests de las políticas de seguridad por fila (RLS) |
| Uso en ordenador y móvil | Los flujos clave (emitir factura, subir gasto, ver trimestre) se completan a 390 px y a 1.440 px de ancho sin scroll horizontal, con accesibilidad Lighthouse ≥ **90** *(propuesto)* | Semana 4 | Tests de extremo a extremo y auditoría Lighthouse |
| Recordatorios | El **100 %** de los avisos de prueba se envía en la fecha prevista para cada plazo *(propuesto)* | Semana 4 | Ejecución del workflow con fechas simuladas |
| Tiempo para registrar una factura de compra | Mediana ≤ **1 min** desde la subida hasta el registro *(propuesto)* | Piloto posterior (8 semanas, ≥ 5 autónomos) | Telemetría: hora de subida y hora de registro |
| Preparación del trimestre | El usuario obtiene sus borradores del 303 y del 130 en ≤ **15 min**, frente a la línea base actual *(propuesto — línea base pendiente de medir)* | Piloto posterior | Telemetría y entrevista al cierre del trimestre |

## 6. Riesgos top 5

| Riesgo | Probabilidad | Impacto | Respuesta y mitigación | Dueño |
| --- | --- | --- | --- | --- |
| El alcance no cabe en cuatro semanas: casi todas las funciones son *Must*, incluidos tres roles, el chatbot, los recordatorios y el reporte | alta | alto | Mitigar. Puertas de control semanales; versión mínima de cada *Must* antes de pulir ninguna (por ejemplo, el panel del gestor como lista de clientes y acceso a sus cuentas, sin funciones propias); reutilizar servicios gestionados (autenticación, correo, gráficos) en lugar de construirlos. Si una puerta falla, renegociar con el equipo docente qué *Must* baja a *Should* | Jorge |
| El chatbot da una respuesta fiscal incorrecta o inventada | alta | alto | Mitigar. Responder solo con fuentes oficiales recuperadas y citarlas; negarse cuando no hay fuente; aviso de que no es asesoramiento; derivación a un asesor; eval continuo con preguntas trampa | Jorge (PO) |
| Error en una regla o en un cálculo fiscal (303, 130, clientes UE y extracomunitarios) | media | alto | Mitigar. Lógica fiscal determinista y con tests, separada del modelo de IA; validar los casos de prueba con el equipo docente o una gestoría; borradores marcados como orientativos | Jorge |
| Fuga de datos entre usuarios, o acceso indebido de un gestor o del administrador a datos fiscales y personales | media | alto | Mitigar. Seguridad por fila en todas las tablas; acceso del gestor solo por invitación del usuario, revocable y con registro de actividad; mínimo privilegio para el administrador; almacenamiento privado; tests de permisos por rol y cumplimiento del RGPD (región UE, contrato de encargado con cada proveedor) | Jorge |
| La lectura de fotos de tickets no alcanza la precisión objetivo | media | medio | Mitigar. Ejemplos en el prompt, escalado a un modelo mayor cuando falla una validación y revisión humana de los datos dudosos; en el peor caso, limitar la versión de la defensa a PDF digitales | Jorge |

## 7. Supuestos
- **Usuario objetivo:** autónomo profesional en estimación directa simplificada, en el régimen general de IVA y en territorio común, que factura sobre todo a empresas con retención de IRPF.
- **Una aplicación online es aceptable:** los usuarios tienen conexión y un móvil con cámara, y están dispuestos a subir sus facturas a la nube si la seguridad es visible.
- **Las facturas son legibles:** la mayoría de las facturas de compra llegan como PDF digital o como foto legible.
- **Las fuentes oficiales bastan:** la documentación de la AEAT y el BOE cubre las dudas fiscales más frecuentes de este perfil de usuario.
- **Los servicios gestionados reducen el trabajo:** la autenticación, los roles y la seguridad por fila de Supabase, junto con un servicio de correo transaccional, evitan construir esas piezas desde cero.
- **El frontend definitivo será Next.js:** el multiusuario, el diseño adaptable y el reporte con gráficos superan lo que Streamlit cubre bien, así que la interfaz se construye en Next.js, diseñada con Claude Design, y Streamlit queda solo para prototipos internos.
- **El gestor trabaja con la cuenta del usuario:** el gestor no tiene una contabilidad propia en la aplicación, sino acceso a las cuentas de los autónomos que le invitan.
- **Equipo y método:** una persona, cuatro semanas, con Claude Code y desarrollo guiado por specs.

## 8. Qué no sabemos todavía
- **Lo que puede hacer el gestor:** ¿solo consulta y revisa, o también puede emitir facturas y registrar gastos en nombre del usuario? ¿Puede marcar un trimestre como presentado? Y, en el plano legal, ¿qué papel tiene en el RGPD cuando accede a los datos de sus clientes?
- **El acceso del administrador para dar soporte:** ¿debe poder ver los datos financieros de un usuario cuando este pide ayuda, y con qué consentimiento?
- **El límite legal del chatbot:** ¿hasta dónde puede responder dudas fiscales sin que se considere asesoramiento profesional, y quién responde si una orientación es errónea?
- **Disposición a pagar:** ¿pagaría un autónomo una suscripción frente a la app gratuita de la AEAT o a TaxDown, que por 14,95 € al mes incluye un asesor que presenta los modelos?
- **Coste unitario:** ¿cuánto cuesta cada usuario al mes entre lectura de facturas, chatbot, correo y alojamiento, y es compatible con un precio de 10 a 15 € al mes?
- **Calendario de VeriFactu:** las fechas vigentes son el 1 de julio de 2027 para autónomos, pero se ha anunciado otro aplazamiento a 2028 sin norma publicada. Esto decide cuándo hay que certificar el software.
- **El contenido útil del reporte mensual:** ¿qué gráficos y cifras consultaría de verdad un autónomo cada mes? Hay que validarlo con usuarios antes de diseñarlo en detalle.
