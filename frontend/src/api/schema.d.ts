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
    "/api/gestor/accesos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Los accesos e invitaciones que el autónomo ha dado, el más reciente primero */
        get: operations["list_gestor_accesses"];
        put?: never;
        /** Invitar a un gestor por correo (la respuesta no revela si el correo es de una cuenta) */
        post: operations["invite_gestor_access"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gestor/accesos/{access_id}/revocar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revocar un acceso o retirar una invitación pendiente (el gestor pierde el acceso al instante) */
        post: operations["revoke_gestor_access"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gestor/invitaciones": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Las invitaciones pendientes dirigidas al gestor, con el nombre de quien invita */
        get: operations["list_gestor_invitations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gestor/invitaciones/{access_id}/aceptar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Aceptar una invitación dirigida al correo del gestor */
        post: operations["accept_gestor_invitation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gestor/invitaciones/{access_id}/rechazar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Rechazar una invitación dirigida al correo del gestor */
        post: operations["decline_gestor_invitation"];
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
    "/api/invoices/{invoice_id}/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Descargar el PDF de una factura, comprobando su huella SHA-256 */
        get: operations["get_invoice_pdf"];
        put?: never;
        /** Generar el PDF de una factura emitida que no lo tiene (idempotente) */
        post: operations["create_invoice_pdf"];
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
    "/api/tax/130": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Borrador orientativo del modelo 130 de un trimestre, acumulado desde enero y con cada casilla enlazada a sus facturas y gastos */
        get: operations["get_modelo_130"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tax/303": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Borrador orientativo del modelo 303 de un trimestre, con cada casilla enlazada a sus facturas y gastos */
        get: operations["get_modelo_303"];
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
        /**
         * ArchivedInput
         * @description `archived` va con `StrictBool`: un `"yes"` no es `true` (B.1-D).
         */
        ArchivedInput: {
            /** Archived */
            archived: boolean;
        };
        /**
         * Box130
         * @description Una casilla del modelo 130. Las derivadas (03, 04 y 07) no llevan documentos: enumeran en `components` las casillas que las componen.
         */
        Box130: {
            /**
             * Amount Cents
             * @description Importe de la casilla, en céntimos y con signo
             */
            amount_cents: number;
            /**
             * Code
             * @description Número de casilla: 01, 02, 03, 04, 05, 06 o 07
             */
            code: string;
            /**
             * Components
             * @description Casillas que componen una derivada; vacío en las demás
             */
            components: string[];
            /**
             * Group
             * @enum {string}
             */
            group: "rendimiento" | "pagos" | "resultado";
            /**
             * Items
             * @description Los documentos que la componen, por fecha; su suma es la casilla
             */
            items: components["schemas"]["Item130"][];
            /** Label */
            label: string;
        };
        /**
         * Box303
         * @description Una casilla del modelo 303. Las derivadas (27, 45 y 46) no llevan documentos: enumeran en `components` las casillas que las componen.
         */
        Box303: {
            /**
             * Amount Cents
             * @description Importe de la casilla, en céntimos y con signo
             */
            amount_cents: number;
            /**
             * Code
             * @description Número de casilla: 01, 03, 04, 06, 07, 09, 27, 28, 29, 45, 46, 59 o 120
             */
            code: string;
            /**
             * Components
             * @description Casillas que componen una derivada; vacío en las demás
             */
            components: string[];
            /**
             * Group
             * @enum {string}
             */
            group: "devengado" | "deducible" | "resultado" | "adicional";
            /**
             * Items
             * @description Los documentos que la componen, por fecha; su suma (según `measure`) es la casilla
             */
            items: components["schemas"]["Item303"][];
            /** Label */
            label: string;
            /**
             * Measure
             * @description Qué importe de cada documento suma en la casilla; `null` en las derivadas
             */
            measure: ("base" | "vat") | null;
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
        /**
         * GestorAccess
         * @description Un acceso (o invitación) que el autónomo ha dado a un gestor.
         */
        GestorAccess: {
            /**
             * Expires At
             * Format: date-time
             * @description Caducidad de la invitación pendiente (14 días desde que se envió)
             */
            expires_at: string;
            /** Gestor Email */
            gestor_email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Invited At
             * Format: date-time
             */
            invited_at: string;
            /**
             * Status
             * @description `expired` es una invitación pendiente cuya fecha de caducidad ya pasó (no es un estado de la base de datos)
             * @enum {string}
             */
            status: "pending" | "active" | "revoked" | "declined" | "expired";
        };
        /**
         * GestorInvitation
         * @description Una invitación pendiente dirigida al gestor que pregunta.
         */
        GestorInvitation: {
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Invited At
             * Format: date-time
             */
            invited_at: string;
            /**
             * Owner Name
             * @description Nombre de quien invita
             */
            owner_name: string;
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
        /**
         * InvitedAccess
         * @description El acceso recién creado. `email_sent` es `false` si el correo no se pudo entregar: la invitación existe igualmente y queda pendiente.
         */
        InvitedAccess: {
            /** Email Sent */
            email_sent: boolean;
            /**
             * Expires At
             * Format: date-time
             * @description Caducidad de la invitación pendiente (14 días desde que se envió)
             */
            expires_at: string;
            /** Gestor Email */
            gestor_email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Invited At
             * Format: date-time
             */
            invited_at: string;
            /**
             * Status
             * @description `expired` es una invitación pendiente cuya fecha de caducidad ya pasó (no es un estado de la base de datos)
             * @enum {string}
             */
            status: "pending" | "active" | "revoked" | "declined" | "expired";
        };
        /**
         * InviteInput
         * @description El correo del gestor. Se recorta y pasa a minúsculas en la base; su formato lo valida la función `app.invite_gestor_access`.
         */
        InviteInput: {
            /**
             * Email
             * @description Correo electrónico del gestor al que se invita
             */
            email: string;
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
            issuer: components["schemas"]["InvoiceIssuer"];
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
         * InvoiceIssuer
         * @description La copia de los datos de la persona emisora que la factura congeló al emitirse: lo mismo que lleva el PDF, no el perfil de ahora.
         */
        InvoiceIssuer: {
            /** Address */
            address: string;
            /** Iban */
            iban: string | null;
            /** Name */
            name: string;
            /** Tax Id */
            tax_id: string;
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
        /**
         * Item130
         * @description Un documento (o un trimestre anterior, en la casilla 05) que compone una casilla, con lo que aporta a ESA casilla (con signo).
         */
        Item130: {
            /**
             * Amount Cents
             * @description Lo que aporta a esta casilla, en céntimos y con signo (negativo en una rectificativa)
             */
            amount_cents: number;
            /**
             * Date
             * Format: date
             * @description Fecha de expedición de la factura o del gasto; el último día del trimestre en un `quarter`
             */
            date: string;
            /**
             * Id
             * @description Identificador de la factura o del gasto; en un trimestre anterior, `T1`, `T2` o `T3`
             */
            id: string;
            /**
             * Kind
             * @description Factura emitida, gasto registrado o trimestre anterior del año (solo en la casilla 05)
             * @enum {string}
             */
            kind: "invoice" | "expense" | "quarter";
            /**
             * Label
             * @description Número de factura, proveedor del gasto o «T1 de 2026»
             */
            label: string;
        };
        /**
         * Item303
         * @description Un documento que compone una casilla, con lo que aporta (negativo en una rectificativa).
         */
        Item303: {
            /** Base Cents */
            base_cents: number;
            /**
             * Date
             * Format: date
             * @description Fecha de expedición de la factura o del gasto
             */
            date: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @description Factura emitida o gasto registrado
             * @enum {string}
             */
            kind: "invoice" | "expense";
            /**
             * Label
             * @description Número de factura o proveedor del gasto
             */
            label: string;
            /** Vat Cents */
            vat_cents: number;
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
         * Modelo130
         * @description El borrador orientativo del 130 de un trimestre, con importes acumulados desde el 1 de enero. No se presenta ante la AEAT desde la aplicación.
         */
        Modelo130: {
            /**
             * Boxes
             * @description Siempre las siete casillas, en el orden de la pantalla, también a cero
             */
            boxes: components["schemas"]["Box130"][];
            /**
             * Deadline
             * Format: date
             * @description Último día de presentación según el calendario (la AEAT lo traslada si cae en un día inhábil)
             */
            deadline: string;
            /**
             * Deadline Status
             * @enum {string}
             */
            deadline_status: "en_curso" | "plazo_abierto" | "plazo_cerrado";
            /**
             * Notes
             * @description Avisos fijos: orientativo, lo que no incluye y la regla del 70 %
             */
            notes: string[];
            /**
             * Period End
             * Format: date
             * @description Primer día del trimestre siguiente (el final es exclusivo)
             */
            period_end: string;
            /**
             * Period Start
             * Format: date
             * @description Primer día del año: el 130 acumula desde el 1 de enero
             */
            period_start: string;
            /**
             * Quarter
             * @description 1 a 4
             */
            quarter: number;
            /**
             * Result Cents
             * @description Casilla 07: 04 − 05 − 06
             */
            result_cents: number;
            /**
             * Result Kind
             * @description `nada_que_ingresar` si hay documentos pero el resultado es 0 o negativo (no se arrastra); `sin_actividad` solo si no hay ningún documento
             * @enum {string}
             */
            result_kind: "a_ingresar" | "nada_que_ingresar" | "sin_actividad";
            /**
             * Withheld Share Percent
             * @description Porcentaje de la casilla 01 que lleva retención, redondeado al entero; `null` si la 01 no es positiva. Solo informativo
             */
            withheld_share_percent: number | null;
            /** Year */
            year: number;
        };
        /**
         * Modelo303
         * @description El borrador orientativo del 303 de un trimestre natural. No se presenta ante la AEAT desde la aplicación.
         */
        Modelo303: {
            /**
             * Boxes
             * @description Siempre las trece casillas, en el orden de la pantalla, también a cero
             */
            boxes: components["schemas"]["Box303"][];
            /**
             * Deadline
             * Format: date
             * @description Último día de presentación según el calendario (la AEAT lo traslada si cae en un día inhábil)
             */
            deadline: string;
            /**
             * Deadline Status
             * @enum {string}
             */
            deadline_status: "en_curso" | "plazo_abierto" | "plazo_cerrado";
            /**
             * Notes
             * @description Avisos fijos: orientativo, lo que no incluye, Canarias, Ceuta y Melilla y, con la casilla 59, el modelo 349
             */
            notes: string[];
            /**
             * Period End
             * Format: date
             * @description Primer día del trimestre siguiente (el final es exclusivo)
             */
            period_end: string;
            /**
             * Period Start
             * Format: date
             * @description Primer día del trimestre
             */
            period_start: string;
            /**
             * Quarter
             * @description 1 a 4
             */
            quarter: number;
            /**
             * Result Cents
             * @description Casilla 46: 27 − 45
             */
            result_cents: number;
            /**
             * Result Kind
             * @description `a_cero` si hay documentos pero el resultado es 0; `sin_actividad` solo si el trimestre no tiene ningún documento
             * @enum {string}
             */
            result_kind: "a_ingresar" | "a_compensar" | "a_cero" | "sin_actividad";
            /** Year */
            year: number;
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
    list_gestor_accesses: {
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
                    "application/json": components["schemas"]["GestorAccess"][];
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
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
    invite_gestor_access: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InviteInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvitedAccess"];
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La invitación o el acceso no está en el estado que esta acción necesita */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Correo no válido, invitación a uno mismo o demasiadas invitaciones abiertas */
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
    revoke_gestor_access: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                access_id: string;
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El acceso o la invitación no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La invitación o el acceso no está en el estado que esta acción necesita */
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
    list_gestor_invitations: {
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
                    "application/json": components["schemas"]["GestorInvitation"][];
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
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
    accept_gestor_invitation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                access_id: string;
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El acceso o la invitación no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La invitación o el acceso no está en el estado que esta acción necesita */
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
    decline_gestor_invitation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                access_id: string;
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
            /** @description El rol de la cuenta no puede usar esta ruta o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description El acceso o la invitación no existe (también si es de otra persona) */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description La invitación o el acceso no está en el estado que esta acción necesita */
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
    get_invoice_pdf: {
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
            /** @description El PDF guardado, con su huella comprobada */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/pdf": string;
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
    create_invoice_pdf: {
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
            /** @description No se puede emitir: cliente archivado o sin domicilio (`client_not_billable`), fecha anterior a la última de la serie (`invoice_date_out_of_order`), rectificativa que sube el importe (`rectification_exceeds`), factura no rectificable o no cobrable, serie agotada o factura cambiada mientras se rectificaba; en el PDF, `invoice_pdf_pending` (aún no tiene) o `invoice_pdf_corrupt` (el archivo no coincide con su huella) */
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
    get_modelo_130: {
        parameters: {
            query?: {
                /** @description Trimestre (1 a 4); por defecto el actual (Europe/Madrid) */
                quarter?: number | null;
                /** @description Año; por defecto el actual (Europe/Madrid) */
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
                    "application/json": components["schemas"]["Modelo130"];
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
            /** @description El rol de la cuenta no puede ver el borrador (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Periodo que no existe (`invalid_period`), trimestre futuro (`period_in_future`) o periodo acumulado con demasiados documentos (`quarter_too_large`) */
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
    get_modelo_303: {
        parameters: {
            query?: {
                /** @description Trimestre (1 a 4); por defecto el actual (Europe/Madrid) */
                quarter?: number | null;
                /** @description Año; por defecto el actual (Europe/Madrid) */
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
                    "application/json": components["schemas"]["Modelo303"];
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
            /** @description El rol de la cuenta no puede ver el borrador (solo `usuario`) o la cuenta está suspendida */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProblemDetails"];
                };
            };
            /** @description Periodo que no existe (`invalid_period`), trimestre futuro (`period_in_future`), trimestre con demasiados documentos (`quarter_too_large`) o un documento con un tipo de IVA que no se puede interpretar (`unsupported_vat_rate`) */
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
