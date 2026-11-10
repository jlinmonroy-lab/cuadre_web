/**
 * GENERADO por `npm run gen:api` a partir de backend/openapi.json. NO se edita a mano.
 * Para cambiarlo: modifica las rutas de la API, ejecuta `python backend/scripts/export_openapi.py` y `npm --prefix frontend run gen:api`.
 */

export interface paths {
    "/api/clients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listar los clientes por nombre (los archivados solo con `include_archived`) */
        get: operations["list_clients"];
        put?: never;
        /** Crear un cliente (todo o nada, con todos los errores a la vez) */
        post: operations["create_client"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients/{client_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtener un cliente */
        get: operations["get_client"];
        /** Sustituir los datos de un cliente activo */
        put: operations["update_client"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients/{client_id}/archived": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Archivar o reactivar un cliente (no se borra) */
        put: operations["set_client_archived"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/clients/billing": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lo facturado a cada cliente en un año (suma de bases con signo) */
        get: operations["get_clients_billing"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
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
    "/api/documents/{document_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Registrar el gasto de un documento si todas las comprobaciones pasan */
        post: operations["confirm_document"];
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
    "/api/expenses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listar los gastos registrados (sin los anulados), del más reciente al más antiguo */
        get: operations["list_expenses"];
        put?: never;
        /** Anotar un gasto sin factura */
        post: operations["create_expense"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/expenses/{expense_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtener un gasto (también uno anulado) */
        get: operations["get_expense"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/expenses/{expense_id}/category": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Cambiar la categoría de un gasto no anulado */
        put: operations["set_expense_category"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/expenses/{expense_id}/void": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Anular un gasto: deja de contar y su documento vuelve a revisión */
        post: operations["void_expense"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoice-series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listar las series de facturación (la predeterminada primero; incluye las archivadas) */
        get: operations["list_invoice_series"];
        put?: never;
        /** Crear una serie */
        post: operations["create_invoice_series"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoice-series/{series_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Cambiar el código, la descripción o el número inicial de una serie, o archivarla y reactivarla */
        patch: operations["update_invoice_series"];
        trace?: never;
    };
    "/api/invoice-series/{series_id}/default": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Hacer predeterminada una serie */
        put: operations["set_default_invoice_series"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Listar las facturas de un año, la más reciente primero */
        get: operations["list_invoices"];
        put?: never;
        /** Emitir una factura (todo o nada, con todos los errores a la vez) */
        post: operations["issue_invoice"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoices/{invoice_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Obtener una factura, con las rectificativas que la corrigen y lo vigente */
        get: operations["get_invoice"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoices/{invoice_id}/payment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Marcar una factura ordinaria como cobrada o pendiente (lo único que cambia en una factura) */
        put: operations["set_invoice_payment"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoices/{invoice_id}/rectifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Emitir una rectificativa por diferencias de la factura indicada */
        post: operations["issue_rectifying_invoice"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/invoices/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Vista previa de una factura: ámbito, importes y mención, sin número y sin escribir nada */
        post: operations["preview_invoice"];
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
    "/api/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Leer el perfil, lo que falta para emitir y la sugerencia de retención (no escribe) */
        get: operations["get_profile"];
        /** Guardar el perfil (todo o nada) y crear la serie del año si falta */
        put: operations["update_profile"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/profile/logo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** URL firmada de 60 s para ver el logo */
        get: operations["get_logo"];
        put?: never;
        /** Reservar una subida de logo y obtener la URL firmada */
        post: operations["upload_logo"];
        /** Quitar el logo y borrar su archivo (idempotente) */
        delete: operations["delete_logo"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/profile/logo/{upload_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Comprobar el logo subido, guardarlo y borrar el anterior */
        post: operations["complete_logo_upload"];
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
        /**
         * ArchivedInput
         * @description `archived` va con `StrictBool`: un `"yes"` no es `true` (B.1-D).
         */
        ArchivedInput: {
            /** Archived */
            archived: boolean;
        };
        /**
         * CheckCode
         * @description Las comprobaciones, en el orden en que se muestran. Son una lista cerrada (§5.1).
         * @enum {string}
         */
        CheckCode: "doc_type" | "required_data" | "doubts_reviewed" | "supplier_tax_id" | "issue_date" | "currency" | "vat_rates" | "vat_amounts" | "withholding" | "total" | "not_duplicate";
        /** CheckItem */
        CheckItem: {
            code: components["schemas"]["CheckCode"];
            /** Detail */
            detail: string | null;
            /** Label */
            label: string;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "failed";
        };
        /** Client */
        Client: {
            /** Address */
            address: string | null;
            /** Archived */
            archived: boolean;
            /** Country */
            country: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "business" | "individual";
            /** Name */
            name: string;
            /**
             * Scope
             * @enum {string}
             */
            scope: "national" | "eu" | "non_eu";
            /** Tax Id */
            tax_id: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * Vies Status
             * @enum {string}
             */
            vies_status: "valid_simulated" | "unchecked" | "not_applicable";
        };
        /**
         * ClientBilling
         * @description Lo facturado a un cliente en un año: la suma de las bases con signo (las rectificativas restan).
         */
        ClientBilling: {
            /** Billed Cents */
            billed_cents: number;
            /**
             * Client Id
             * Format: uuid
             */
            client_id: string;
        };
        /**
         * ClientInput
         * @description Los campos de §5.1. Los ausentes valen `null` y el dominio dice cuáles hacen falta.
         */
        ClientInput: {
            /** Address */
            address?: string | null;
            /** Country */
            country?: string | null;
            /** Kind */
            kind?: string | null;
            /** Name */
            name?: string | null;
            /** Tax Id */
            tax_id?: string | null;
        };
        /** Completeness */
        Completeness: {
            /** Can Issue */
            can_issue: boolean;
            /** Missing For Invoicing */
            missing_for_invoicing: components["schemas"]["MissingField"][];
        };
        /**
         * ConfirmRequest
         * @description `acknowledge_suspicion`: la persona confirma que comparó los datos con el original (solo se exige si hay sospecha, NFR-07).
         */
        ConfirmRequest: {
            /**
             * Acknowledge Suspicion
             * @default false
             */
            acknowledge_suspicion: boolean;
            category: components["schemas"]["ExpenseCategory"];
        };
        /** CreateExpense */
        CreateExpense: {
            /** Amount Cents */
            amount_cents: number;
            category: components["schemas"]["ExpenseCategory"];
            /** Concept */
            concept: string;
            /**
             * Expense Date
             * Format: date
             */
            expense_date: string;
        };
        /** Document */
        Document: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error: components["schemas"]["DocumentError"] | null;
            /** Expense Id */
            expense_id: string | null;
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
            validation: components["schemas"]["Validation"] | null;
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
        /** Expense */
        Expense: {
            /** Base Cents */
            base_cents: number;
            category: components["schemas"]["ExpenseCategory"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Deductible Vat */
            deductible_vat: boolean;
            /** Doc Type */
            doc_type: ("full_invoice" | "simplified_invoice" | "ticket" | "receipt") | null;
            /** Document Id */
            document_id: string | null;
            /**
             * Expense Date
             * Format: date
             */
            expense_date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Invoice Number */
            invoice_number: string | null;
            /**
             * Origin
             * @enum {string}
             */
            origin: "document" | "manual";
            /** Supplier Name */
            supplier_name: string;
            /** Supplier Scope */
            supplier_scope: ("national" | "eu") | null;
            /** Supplier Tax Id */
            supplier_tax_id: string | null;
            /** Suspicion Acknowledged */
            suspicion_acknowledged: boolean;
            /** Tax Breakdown */
            tax_breakdown: components["schemas"]["ExpenseTaxLine"][];
            /** Total Cents */
            total_cents: number;
            /** Vat Cents */
            vat_cents: number;
            /** Voided At */
            voided_at: string | null;
            /** Withholding Cents */
            withholding_cents: number;
        };
        /**
         * ExpenseCategory
         * @enum {string}
         */
        ExpenseCategory: "software" | "workspace" | "supplies" | "utilities" | "advisory" | "self_employed_fee" | "training" | "other";
        /** ExpensePage */
        ExpensePage: {
            /** Items */
            items: components["schemas"]["ExpenseSummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * ExpenseSummary
         * @description Una fila de «Gastos registrados».
         */
        ExpenseSummary: {
            category: components["schemas"]["ExpenseCategory"];
            /** Deductible Vat */
            deductible_vat: boolean;
            /** Document Id */
            document_id: string | null;
            /**
             * Expense Date
             * Format: date
             */
            expense_date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Origin
             * @enum {string}
             */
            origin: "document" | "manual";
            /** Supplier Name */
            supplier_name: string;
            /** Supplier Scope */
            supplier_scope: ("national" | "eu") | null;
            /** Total Cents */
            total_cents: number;
            /** Vat Cents */
            vat_cents: number;
        };
        /** ExpenseTaxLine */
        ExpenseTaxLine: {
            /** Base Cents */
            base_cents: number;
            /** Vat Cents */
            vat_cents: number;
            /** Vat Rate */
            vat_rate: string;
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
        /** Invoice */
        Invoice: {
            /** Base Cents */
            base_cents: number;
            client: components["schemas"]["InvoiceClient"];
            /** Concept */
            concept: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Display Number */
            display_number: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Irpf Cents */
            irpf_cents: number;
            /** Irpf Rate */
            irpf_rate: string;
            /**
             * Issue Date
             * Format: date
             */
            issue_date: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "standard" | "rectifying";
            /** Legal Note */
            legal_note: string | null;
            /** Number */
            number: number;
            /** Paid At */
            paid_at: string | null;
            /**
             * Pdf Status
             * @enum {string}
             */
            pdf_status: "ready" | "pending";
            /** Rectification Reason */
            rectification_reason: string | null;
            /** Rectified By */
            rectified_by: string[];
            rectifies: components["schemas"]["InvoiceRef"] | null;
            /** Series Code */
            series_code: string;
            standing: components["schemas"]["Standing"] | null;
            /**
             * Tax Treatment
             * @enum {string}
             */
            tax_treatment: "national_vat" | "eu_reverse_charge" | "eu_consumer_vat" | "non_eu_consumer_vat" | "non_eu_not_subject";
            /** Total Cents */
            total_cents: number;
            /** Vat Cents */
            vat_cents: number;
            /** Vat Rate */
            vat_rate: string;
        };
        /**
         * InvoiceClient
         * @description La copia del cliente que la factura congeló al emitirse (D-09).
         */
        InvoiceClient: {
            /** Address */
            address: string;
            /** Country */
            country: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "business" | "individual";
            /** Name */
            name: string;
            /**
             * Scope
             * @enum {string}
             */
            scope: "national" | "eu" | "non_eu";
            /** Tax Id */
            tax_id: string | null;
        };
        /**
         * InvoiceInput
         * @description Los campos de §5.1.1. Los ausentes valen `null` y el dominio dice cuáles hacen falta; `series_id` vacío es la serie predeterminada.
         */
        InvoiceInput: {
            /** Base Cents */
            base_cents?: number | null;
            /** Client Id */
            client_id?: string | null;
            /** Concept */
            concept?: string | null;
            /** Issue Date */
            issue_date?: string | null;
            /** Series Id */
            series_id?: string | null;
            /** Vat Rate */
            vat_rate?: string | null;
        };
        /**
         * InvoicePreview
         * @description Lo que se emitiría, sin número ni nada escrito (§5.3). El navegador lo enseña y no calcula impuestos.
         */
        InvoicePreview: {
            /** Base Cents */
            base_cents: number;
            /** Irpf Cents */
            irpf_cents: number;
            /** Irpf Rate */
            irpf_rate: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "business" | "individual";
            /** Legal Note */
            legal_note: string | null;
            /**
             * Scope
             * @enum {string}
             */
            scope: "national" | "eu" | "non_eu";
            /**
             * Tax Treatment
             * @enum {string}
             */
            tax_treatment: "national_vat" | "eu_reverse_charge" | "eu_consumer_vat" | "non_eu_consumer_vat" | "non_eu_not_subject";
            /** Total Cents */
            total_cents: number;
            /** Vat Cents */
            vat_cents: number;
            /** Vat Editable */
            vat_editable: boolean;
            /** Vat Rate */
            vat_rate: string;
        };
        /** InvoiceRef */
        InvoiceRef: {
            /** Display Number */
            display_number: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Issue Date
             * Format: date
             */
            issue_date: string;
        };
        /** InvoiceSeries */
        InvoiceSeries: {
            /** Archived */
            archived: boolean;
            /** Code */
            code: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string | null;
            /** First Number */
            first_number: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** In Use */
            in_use: boolean;
            /** Is Default */
            is_default: boolean;
            /** Next Number */
            next_number: number;
        };
        /** LogoUploadInstructions */
        LogoUploadInstructions: {
            /** Headers */
            headers: {
                [key: string]: string;
            };
            /** Url */
            url: string;
        };
        /** LogoUploadRequest */
        LogoUploadRequest: {
            /** Mime Type */
            mime_type: string;
            /** Size Bytes */
            size_bytes: number;
        };
        /** LogoUploadResponse */
        LogoUploadResponse: {
            upload: components["schemas"]["LogoUploadInstructions"];
            /**
             * Upload Id
             * Format: uuid
             */
            upload_id: string;
        };
        /** LogoUrl */
        LogoUrl: {
            /**
             * Expires In
             * @default 60
             * @constant
             */
            expires_in: 60;
            /** Url */
            url: string;
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
        /** MissingField */
        MissingField: {
            /**
             * Field
             * @enum {string}
             */
            field: "legal_name" | "tax_id" | "fiscal_address";
            /** Label */
            label: string;
        };
        /**
         * PaymentInput
         * @description `paid` va con `StrictBool`: un `"yes"` no es `true`.
         */
        PaymentInput: {
            /** Paid */
            paid: boolean;
        };
        /** Preview */
        Preview: {
            /** Deductible Note */
            deductible_note: string | null;
            /** Deductible Vat */
            deductible_vat: boolean;
            suggested_category: components["schemas"]["ExpenseCategory"];
            /** Supplier Scope */
            supplier_scope: ("national" | "eu") | null;
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
        /** Profile */
        Profile: {
            /** Activity */
            activity: string | null;
            /** Activity Start Date */
            activity_start_date: string | null;
            completeness: components["schemas"]["Completeness"];
            /** Fiscal Address */
            fiscal_address: string | null;
            /** Has Logo */
            has_logo: boolean;
            /** Home Pct */
            home_pct: string | null;
            /** Iae Epigraph */
            iae_epigraph: string | null;
            /** Iban */
            iban: string | null;
            /** Irpf Rate */
            irpf_rate: ("7.00" | "15.00") | null;
            /** Legal Name */
            legal_name: string | null;
            retention: components["schemas"]["Retention"];
            /** Tax Id */
            tax_id: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * Vat Regime
             * @constant
             */
            vat_regime: "general";
        };
        /**
         * ProfileInput
         * @description Los campos de §5.1. Los ausentes valen `null`. Los textos se validan en `cuadre.profile` (no aquí) para devolver todos los
         *     errores juntos y con sus mensajes.
         */
        ProfileInput: {
            /** Activity */
            activity?: string | null;
            /** Activity Start Date */
            activity_start_date?: string | null;
            /** Fiscal Address */
            fiscal_address?: string | null;
            /** Home Pct */
            home_pct?: string | null;
            /** Iae Epigraph */
            iae_epigraph?: string | null;
            /** Iban */
            iban?: string | null;
            /** Irpf Rate */
            irpf_rate?: string | null;
            /** Legal Name */
            legal_name?: string | null;
            /** Tax Id */
            tax_id?: string | null;
            /** Vat Regime */
            vat_regime?: string | null;
        };
        /** RectificationInput */
        RectificationInput: {
            /** Corrected Base Cents */
            corrected_base_cents?: number | null;
            /** Issue Date */
            issue_date?: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** Retention */
        Retention: {
            /** Reduced Until Year */
            reduced_until_year: number | null;
            /** Suggested Rate */
            suggested_rate: ("7.00" | "15.00") | null;
            /** Warning */
            warning: string | null;
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
        /** SeriesCreate */
        SeriesCreate: {
            /** Code */
            code: string;
            /** Description */
            description?: string | null;
            /** First Number */
            first_number?: number | null;
            /**
             * Make Default
             * @default false
             */
            make_default: boolean;
        };
        /**
         * SeriesUpdate
         * @description Solo lo que cambia: una clave ausente no se toca y `description: null` la borra.
         */
        SeriesUpdate: {
            /** Archived */
            archived?: boolean | null;
            /** Code */
            code?: string | null;
            /** Description */
            description?: string | null;
            /** First Number */
            first_number?: number | null;
        };
        /** SetCategory */
        SetCategory: {
            category: components["schemas"]["ExpenseCategory"];
        };
        /**
         * Standing
         * @description Lo vigente de una factura tras sus rectificativas (§5.1.5).
         */
        Standing: {
            /** Base Cents */
            base_cents: number;
            /** Irpf Cents */
            irpf_cents: number;
            /** Vat Cents */
            vat_cents: number;
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
        /** Validation */
        Validation: {
            /** Can Register */
            can_register: boolean;
            /** Checks */
            checks: components["schemas"]["CheckItem"][];
            preview: components["schemas"]["Preview"];
            /** Requires Acknowledgement */
            requires_acknowledgement: boolean;
            /** Warnings */
            warnings: components["schemas"]["WarningItem"][];
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
        /** VoidResult */
        VoidResult: {
            /** Document Id */
            document_id: string | null;
            /** Document Status */
            document_status: ("uploading" | "processing" | "review" | "extraction_failed" | "discarded" | "registered") | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /**
         * WarningCode
         * @description Avisos que nunca bloquean.
         * @enum {string}
         */
        WarningCode: "possible_duplicate" | "recipient_mismatch" | "eu_supplier";
        /** WarningItem */
        WarningItem: {
            code: components["schemas"]["WarningCode"];
            /** Message */
            message: string;
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
    list_clients: {
        parameters: {
            query?: {
                include_archived?: boolean;
            };
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
                    "application/json": components["schemas"]["Client"][];
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
            /** @description El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida */
            403: {
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
    create_client: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Client"];
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
            /** @description El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Ya hay otro cliente activo con ese identificador fiscal, o el cliente está archivado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`fields` enumera todos los campos que fallan) */
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
    get_client: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
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
                    "application/json": components["schemas"]["Client"];
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
            /** @description El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El cliente no existe (también si es de otra persona) */
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
    update_client: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Client"];
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
            /** @description El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El cliente no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Ya hay otro cliente activo con ese identificador fiscal, o el cliente está archivado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`fields` enumera todos los campos que fallan) */
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
    set_client_archived: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArchivedInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Client"];
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
            /** @description El rol de la cuenta no puede usar clientes (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El cliente no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Ya hay otro cliente activo con ese identificador fiscal, o el cliente está archivado */
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
    get_clients_billing: {
        parameters: {
            query?: {
                /** @description Año de expedición; por defecto el actual (Europe/Madrid) */
                year?: number | null;
            };
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
                    "application/json": components["schemas"]["ClientBilling"][];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir (`irpf_rate_missing`) */
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
            /** @description Datos no válidos, archivo que no es del tipo indicado o comprobaciones sin pasar */
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, archivo que no es del tipo indicado o comprobaciones sin pasar */
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
    confirm_document: {
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
                "application/json": components["schemas"]["ConfirmRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Expense"];
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, archivo que no es del tipo indicado o comprobaciones sin pasar */
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
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
            /** @description El documento no está en un estado que admita esa acción, o ya hay un gasto con esa factura */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, archivo que no es del tipo indicado o comprobaciones sin pasar */
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
    list_expenses: {
        parameters: {
            query?: {
                category?: components["schemas"]["ExpenseCategory"] | null;
                cursor?: string | null;
                limit?: number;
                month?: number | null;
                year?: number | null;
            };
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
                    "application/json": components["schemas"]["ExpensePage"];
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
            /** @description El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, comprobaciones sin pasar o fecha fuera de rango */
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
    create_expense: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateExpense"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Expense"];
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
            /** @description El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, comprobaciones sin pasar o fecha fuera de rango */
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
    get_expense: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                expense_id: string;
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
                    "application/json": components["schemas"]["Expense"];
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
            /** @description El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El gasto no existe (también si es de otra persona) */
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
    set_expense_category: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                expense_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetCategory"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Expense"];
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
            /** @description El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El gasto no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El gasto está anulado o el documento no admite esa acción */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos, comprobaciones sin pasar o fecha fuera de rango */
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
    void_expense: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                expense_id: string;
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
                    "application/json": components["schemas"]["VoidResult"];
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
            /** @description El rol de la cuenta no puede usar gastos (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El gasto no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El gasto está anulado o el documento no admite esa acción */
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
    list_invoice_series: {
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
                    "application/json": components["schemas"]["InvoiceSeries"][];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
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
    create_invoice_series: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SeriesCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvoiceSeries"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Código de serie en uso, serie en uso, predeterminada o archivada */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado */
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
    update_invoice_series: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                series_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SeriesUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvoiceSeries"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La serie no existe (también si es de otra persona) o no hay logo */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Código de serie en uso, serie en uso, predeterminada o archivada */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado */
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
    set_default_invoice_series: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                series_id: string;
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
                    "application/json": components["schemas"]["InvoiceSeries"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La serie no existe (también si es de otra persona) o no hay logo */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Código de serie en uso, serie en uso, predeterminada o archivada */
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
    list_invoices: {
        parameters: {
            query?: {
                /** @description Solo ordinarias cobradas o pendientes de cobro */
                paid?: boolean | null;
                /** @description Ámbito del cliente */
                scope?: ("national" | "eu" | "non_eu") | null;
                /** @description Año de expedición; por defecto el actual (Europe/Madrid) */
                year?: number | null;
            };
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
                    "application/json": components["schemas"]["Invoice"][];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir (`irpf_rate_missing`) */
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
    issue_invoice: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InvoiceInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Invoice"];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir (`irpf_rate_missing`) */
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
    get_invoice: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                invoice_id: string;
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
                    "application/json": components["schemas"]["Invoice"];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La factura no existe (también si es de otra persona) */
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
    set_invoice_payment: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                invoice_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaymentInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Invoice"];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La factura no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba */
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
    issue_rectifying_invoice: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                invoice_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RectificationInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Invoice"];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La factura no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir (`irpf_rate_missing`) */
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
    preview_invoice: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InvoiceInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvoicePreview"];
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
            /** @description El rol de la cuenta no puede usar facturas (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (`invalid_invoice` con `fields`), perfil incompleto (`profile_incomplete` con `missing`) o retención sin elegir (`irpf_rate_missing`) */
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
    get_profile: {
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
                    "application/json": components["schemas"]["Profile"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
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
    update_profile: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Profile"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado */
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
    get_logo: {
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
                    "application/json": components["schemas"]["LogoUrl"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La serie no existe (también si es de otra persona) o no hay logo */
            404: {
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
    upload_logo: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LogoUploadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LogoUploadResponse"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El logo supera 1 MiB */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El logo no es PNG, JPEG ni WebP */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado */
            422: {
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
    delete_logo: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
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
    complete_logo_upload: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
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
                    "application/json": components["schemas"]["Profile"];
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
            /** @description El rol de la cuenta no puede usar el perfil (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Datos no válidos (con `fields` o `field` según el caso) o logo que no es del tipo indicado */
            422: {
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
