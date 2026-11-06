/**
 * GENERADO por `npm run gen:api` a partir de backend/openapi.json. NO se edita a mano.
 * Para cambiarlo: modifica las rutas de la API, ejecuta `python backend/scripts/export_openapi.py` y `npm --prefix frontend run gen:api`.
 */

export interface paths {
    "/api/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listar los documentos de la persona */
        get: operations["list_documents"];
        put?: never;
        /** Reservar un documento y obtener la URL firmada para subir el archivo */
        post: operations["upload_document"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtener un documento con su lectura y sus correcciones */
        get: operations["get_document"];
        put?: never;
        post?: never;
        /** Descartar un documento y borrar su archivo */
        delete: operations["discard_document"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Comprobar el archivo subido y leerlo (espera al agente) */
        post: operations["complete_document_upload"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** URL firmada de 60 s para ver el original */
        get: operations["get_document_preview"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Volver a leer un documento que falló (espera al agente) */
        post: operations["retry_document_extraction"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Guardar las correcciones de la persona (la lectura original no cambia) */
        put: operations["save_document_review"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtener la cuenta autenticada y su rol */
        get: operations["get_me"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Comprobar que la API responde */
        get: operations["get_health"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Document */
        Document: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error: components["schemas"]["DocumentError"] | null;
            /** Extracted At */
            extracted_at: string | null;
            extraction: components["schemas"]["Extraction"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Injection Suspected */
            injection_suspected: boolean;
            /** Mime Type */
            mime_type: string;
            /** Original Filename */
            original_filename: string;
            review: components["schemas"]["Review"] | null;
            /** Size Bytes */
            size_bytes: number;
            /**
             * Source
             * @enum {string}
             */
            source: "file" | "camera";
            /**
             * Status
             * @enum {string}
             */
            status: "uploading" | "processing" | "review" | "extraction_failed" | "discarded" | "registered";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Uploaded At */
            uploaded_at: string | null;
        };
        /** DocumentError */
        DocumentError: {
            /**
             * Code
             * @enum {string}
             */
            code: "unreadable" | "unsupported_media_type" | "payload_too_large" | "timeout" | "upstream_error" | "agents_unavailable" | "invalid_response" | "internal";
            /** Message */
            message: string;
        };
        /** DocumentState */
        DocumentState: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "uploading" | "processing" | "review" | "extraction_failed" | "discarded" | "registered";
        };
        /**
         * DocumentSummary
         * @description Una fila de la lista de Gastos.
         */
        DocumentSummary: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Doc Type */
            doc_type: ("full_invoice" | "simplified_invoice" | "ticket" | "receipt" | "other" | "not_an_invoice") | null;
            /** Doubtful Count */
            doubtful_count: number;
            error: components["schemas"]["DocumentError"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Injection Suspected */
            injection_suspected: boolean;
            /** Mime Type */
            mime_type: string;
            /** Original Filename */
            original_filename: string;
            /**
             * Status
             * @enum {string}
             */
            status: "uploading" | "processing" | "review" | "extraction_failed" | "discarded" | "registered";
            /** Supplier Name */
            supplier_name: string | null;
            /** Total Cents */
            total_cents: number | null;
        };
        /** DoubtfulField */
        DoubtfulField: {
            /**
             * Field
             * @enum {string}
             */
            field: "doc_type" | "supplier_name" | "supplier_tax_id" | "recipient_tax_id" | "invoice_number" | "issue_date" | "currency" | "tax_breakdown" | "withholding" | "total";
            /** Line Index */
            line_index: number | null;
            /** Raw Text */
            raw_text: string | null;
            /**
             * Reason
             * @enum {string}
             */
            reason: "illegible" | "ambiguous" | "missing" | "inconsistent";
        };
        /**
         * Extraction
         * @description La lectura del agente ya normalizada. Es de solo lectura: la persona corrige en `Review`.
         */
        Extraction: {
            /** Currency */
            currency: string | null;
            /**
             * Doc Type
             * @enum {string}
             */
            doc_type: "full_invoice" | "simplified_invoice" | "ticket" | "receipt" | "other" | "not_an_invoice";
            /** Doubtful Fields */
            doubtful_fields: components["schemas"]["DoubtfulField"][];
            /** Invoice Number */
            invoice_number: string | null;
            /** Issue Date */
            issue_date: string | null;
            /** Recipient Tax Id */
            recipient_tax_id: string | null;
            /** Supplier Name */
            supplier_name: string | null;
            /** Supplier Tax Id */
            supplier_tax_id: string | null;
            /** Tax Breakdown */
            tax_breakdown: components["schemas"]["TaxLine"][];
            /** Total Cents */
            total_cents: number | null;
            /** Warnings */
            warnings: string[];
            withholding: components["schemas"]["Withholding"] | null;
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Status
             * @constant
             */
            status: "ok";
            /** Version */
            version: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** MeResponse */
        MeResponse: {
            /** Display Name */
            display_name: string;
            /** Email */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Role
             * @enum {string}
             */
            role: "usuario" | "gestor" | "admin";
            /**
             * Status
             * @constant
             */
            status: "active";
        };
        /** PreviewResponse */
        PreviewResponse: {
            /** Expires In */
            expires_in: number;
            /** Previewable */
            previewable: boolean;
            /** Url */
            url: string;
        };
        /**
         * ProblemDetails
         * @description Forma de todo error de la API. Se declara para que aparezca en OpenAPI.
         */
        ProblemDetails: {
            /** Code */
            code: string;
            /** Detail */
            detail: string;
            /** Request Id */
            request_id?: string | null;
            /** Status */
            status: number;
            /** Title */
            title: string;
            /**
             * Type
             * @default about:blank
             */
            type: string;
        };
        /** Review */
        Review: {
            /** Currency */
            currency?: string | null;
            /** Doc Type */
            doc_type?: ("full_invoice" | "simplified_invoice" | "ticket" | "receipt" | "other" | "not_an_invoice") | null;
            /** Invoice Number */
            invoice_number?: string | null;
            /** Issue Date */
            issue_date?: string | null;
            /** Recipient Tax Id */
            recipient_tax_id?: string | null;
            /** Supplier Name */
            supplier_name?: string | null;
            /** Supplier Tax Id */
            supplier_tax_id?: string | null;
            /** Tax Breakdown */
            tax_breakdown?: components["schemas"]["ReviewTaxLine"][];
            /** Total Cents */
            total_cents?: number | null;
            withholding?: components["schemas"]["ReviewWithholding"] | null;
        };
        /** ReviewTaxLine */
        ReviewTaxLine: {
            /** Base Cents */
            base_cents?: number | null;
            /** Vat Cents */
            vat_cents?: number | null;
            /** Vat Rate */
            vat_rate?: string | null;
        };
        /** ReviewWithholding */
        ReviewWithholding: {
            /** Amount Cents */
            amount_cents?: number | null;
            /** Rate */
            rate?: string | null;
        };
        /** TaxLine */
        TaxLine: {
            /** Base Cents */
            base_cents: number | null;
            /** Vat Cents */
            vat_cents: number | null;
            /** Vat Rate */
            vat_rate: string | null;
        };
        /** UploadInstructions */
        UploadInstructions: {
            /** Headers */
            headers: {
                [key: string]: string;
            };
            /**
             * Method
             * @constant
             */
            method: "PUT";
            /** Url */
            url: string;
        };
        /**
         * UploadRequest
         * @description `mime_type` es una cadena, no una enumeración: un tipo no permitido es un 415 propio, no un 422 genérico.
         */
        UploadRequest: {
            /** Filename */
            filename: string;
            /** Mime Type */
            mime_type: string;
            /** Size Bytes */
            size_bytes: number;
            /**
             * Source
             * @enum {string}
             */
            source: "file" | "camera";
        };
        /** UploadResponse */
        UploadResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Max Bytes */
            max_bytes: number;
            /**
             * Status
             * @constant
             */
            status: "uploading";
            upload: components["schemas"]["UploadInstructions"];
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** Withholding */
        Withholding: {
            /** Amount Cents */
            amount_cents: number | null;
            /** Rate */
            rate: string | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_documents: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentSummary"][];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    upload_document: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadResponse"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El archivo supera el máximo de 15 MB */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Tipo de archivo no admitido */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos o archivo que no es del tipo indicado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Demasiadas lecturas en curso (con `Retry-After`) */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Almacenamiento no disponible */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    get_document: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Document"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discard_document: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no está en un estado que admita esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_document_upload: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentState"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no está en un estado que admita esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos o archivo que no es del tipo indicado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Demasiadas lecturas en curso (con `Retry-After`) */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Almacenamiento no disponible */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    get_document_preview: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewResponse"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no está en un estado que admita esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Almacenamiento no disponible */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    retry_document_extraction: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentState"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no está en un estado que admita esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description Demasiadas lecturas en curso (con `Retry-After`) */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Almacenamiento no disponible */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    save_document_review: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Review"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Document"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El rol de la cuenta no puede usar documentos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El documento no está en un estado que admita esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos o archivo que no es del tipo indicado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    get_me: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
            /** @description Sin sesión, o sesión inválida o caducada */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Cuenta suspendida o sin perfil */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description No se puede comprobar la sesión ahora mismo */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
        };
    };
    get_health: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
}
