"""Constantes del chat (SPEC-W-004 §5.1, D-12; P-03: provisionales, un solo sitio para ajustarlas con datos reales).

Los plazos del agente (15 s hasta el primer frame, 90 s en total) viven en `cuadre.agents.http`: este paquete no puede importarse desde allí.
La longitud de 8.000 caracteres de cada mensaje es la del contrato C2 y la de la CHECK de `chat_messages`; el tope de 2.000 del mensaje de la persona
solo existe aquí (la base de datos admite 8.000).
"""

MAX_MESSAGE_CHARS = 2_000  # lo que puede escribir la persona
MAX_BODY_CHARS = 8_000  # por encima, `422 validation_error` de Pydantic: ni se mira
MAX_REPLY_CHARS = 8_000  # lo que se guarda de una respuesta: es lo que el contrato admite al devolverla como historial
CONTEXT_MESSAGES = 50  # el contrato admite hasta 50 mensajes por petición
MESSAGES_PER_HOUR = 20  # mensajes de la persona por hora (D-12); lo aplica la base de datos con un cerrojo por persona
MAX_CITATIONS = 20  # por respuesta
TITLE_CHARS = 60
LIST_LIMIT = 200  # conversaciones en la lista
THREAD_LIMIT = 500  # mensajes de una conversación que se devuelven (los más recientes)
MAX_TOOL_NAME_CHARS = 100

RETRY_AFTER_FALLBACK_SECONDS = 60  # si no se puede calcular cuándo se libera un hueco
MAX_RETRY_AFTER_SECONDS = 3_600  # la ventana del tope
RETRY_AFTER_AGENT_UNAVAILABLE = 5  # segundos que sugiere el `503` cuando el agente no responde
