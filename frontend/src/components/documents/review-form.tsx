"use client";

import { CircleCheck, Plus, TriangleAlert, X } from "lucide-react";
import { useActionState, useState, type ReactNode } from "react";

import type { components } from "@/api/schema";
import { useDirty } from "@/components/expenses/dirty-context";
import { ErrorSummary } from "@/components/error-summary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DOC_TYPES, DOC_TYPE_LABELS, DOUBT_FIELD_LABELS, doubtReasonText } from "@/lib/documents";
import { saveReview } from "@/lib/documents-actions";
import { initialFormState, type FormState } from "@/lib/form-state";
import { MAX_LINES, lineName, type FormValues } from "@/lib/review";
import { cn } from "@/lib/utils";

type Doubt = components["schemas"]["DoubtfulField"];
type Line = { rate: string; base: string; vat: string };

const DOUBTFUL = "border-status-doubt-line bg-status-doubt-bg";
const AMOUNT = "text-right tabular-nums";

function DoubtNote({ id, doubt }: { id: string; doubt: Doubt }) {
  return (
    <p id={id} className="flex items-start gap-1.5 text-xs font-semibold text-status-doubt">
      <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
      <span>
        {doubtReasonText(doubt.reason)}
        {doubt.raw_text ? (
          <>
            {" "}
            Se leyó: <q>{doubt.raw_text}</q>.
          </>
        ) : null}
      </span>
    </p>
  );
}

type FieldProps = {
  name: string;
  label: string;
  error?: string | undefined;
  doubt?: Doubt | undefined;
  hint?: string;
  className?: string;
  /** El control (input o select): recibe el `id` y los `aria-*` calculados aquí. */
  children: (control: { id: string; "aria-invalid": true | undefined; "aria-describedby": string | undefined }) => ReactNode;
};

/** Etiqueta + control + ayuda + duda + error, enlazados con `aria-describedby`. Una duda se marca con icono y texto; el color refuerza. */
function ReviewField({ name, label, error, doubt, hint, className, children }: FieldProps) {
  const id = `review-${name}`;
  const hintId = `${id}-hint`;
  const doubtId = `${id}-doubt`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, doubt ? doubtId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("grid content-start gap-1.5", className)}>
      <Label htmlFor={id} className="text-[13px] font-semibold text-ink-soft">
        {label}
      </Label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
      {doubt ? <DoubtNote id={doubtId} doubt={doubt} /> : null}
      {error ? (
        <p id={errorId} className="text-[13px] font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

const firstDoubt = (doubts: Doubt[], field: string, lineIndex?: number) =>
  doubts.find((doubt) => doubt.field === field && (lineIndex === undefined || doubt.line_index === lineIndex));

type Props = {
  documentId: string;
  /** Valores con los que se pinta el formulario (`review ?? extraction`, ver `initialValues`). */
  initial: FormValues;
  doubts: Doubt[];
  /** Acciones del pie que no son de este formulario (volver a leer, descartar). */
  actions?: ReactNode;
};

export function ReviewForm({ documentId, initial, doubts, actions }: Props) {
  const { setDirty } = useDirty();
  // Guardar con éxito deja el formulario "limpio": las comprobaciones del panel vuelven a ser las de lo que se ve. Un guardado con error no.
  const [state, action, pending] = useActionState(async (previous: FormState, formData: FormData) => {
    const next = await saveReview(documentId, previous, formData);
    if (next.status === "sent") setDirty(false);
    return next;
  }, initialFormState);
  const values = state.values ?? initial;
  const errors = state.fieldErrors ?? {};
  const [lines, setLines] = useState<Line[]>(() => {
    const count = Number.parseInt(initial["line_count"] ?? "1", 10) || 1;
    return Array.from({ length: count }, (_, i) => ({
      rate: initial[lineName(i, "rate")] ?? "",
      base: initial[lineName(i, "base")] ?? "",
      vat: initial[lineName(i, "vat")] ?? "",
    }));
  });
  // Los errores por línea llevan el número de línea de CUANDO se envió: tras añadir o quitar una, ya no valen hasta el siguiente envío.
  const [editedAt, setEditedAt] = useState<unknown>(null);
  const lineErrorsVisible = editedAt !== state;

  const change = (index: number, part: keyof Line, value: string) => {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, [part]: value } : line)));
  };
  const structure = (next: (current: Line[]) => Line[]) => {
    setLines(next);
    setEditedAt(state);
    setDirty(true);
  };

  const fieldIds: Record<string, string> = {};
  for (const name of ["doc_type", "supplier_name", "supplier_tax_id", "recipient_tax_id", "invoice_number", "issue_date", "currency", "total", "withholding_rate", "withholding_amount"]) {
    fieldIds[name] = `review-${name}`;
  }
  if (lineErrorsVisible) {
    lines.forEach((_, i) => {
      for (const part of ["rate", "base", "vat"] as const) fieldIds[lineName(i, part)] = `review-${lineName(i, part)}`;
    });
  }
  fieldIds["line_count"] = "review-add-line";

  const text = (name: string, label: string, options: { maxLength: number; doubtField: string }) => (
    <ReviewField name={name} label={label} error={errors[name]} doubt={firstDoubt(doubts, options.doubtField)}>
      {(control) => (
        <Input
          {...control}
          name={name}
          defaultValue={values[name] ?? ""}
          maxLength={options.maxLength}
          autoComplete="off"
          className={cn(firstDoubt(doubts, options.doubtField) && DOUBTFUL)}
        />
      )}
    </ReviewField>
  );

  const amount = (name: string, label: string, doubtField?: string) => {
    const doubt = doubtField ? firstDoubt(doubts, doubtField) : undefined;
    return (
      <ReviewField name={name} label={label} error={errors[name]} doubt={doubt}>
        {(control) => (
          <Input {...control} name={name} defaultValue={values[name] ?? ""} inputMode="decimal" autoComplete="off" placeholder="Ej.: 1.234,50" className={cn(AMOUNT, doubt && DOUBTFUL)} />
        )}
      </ReviewField>
    );
  };

  return (
    <form action={action} noValidate onChange={() => setDirty(true)} className="grid gap-6">
      <ErrorSummary state={state} fieldIds={fieldIds} />
      {state.status === "sent" ? (
        <p role="status" className="flex items-center gap-2 rounded-md border border-status-ok bg-status-ok-bg px-3 py-2.5 text-sm font-semibold text-status-ok">
          <CircleCheck aria-hidden="true" className="size-4 shrink-0" />
          {state.message}
        </p>
      ) : null}

      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(190px,1fr))]">
        <ReviewField name="doc_type" label="Tipo de documento" error={errors["doc_type"]} doubt={firstDoubt(doubts, "doc_type")}>
          {(control) => (
            <select
              {...control}
              name="doc_type"
              defaultValue={values["doc_type"] ?? ""}
              className={cn(
                "h-10 w-full min-w-0 rounded-lg border border-input bg-white px-3 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/60 aria-invalid:border-destructive",
                firstDoubt(doubts, "doc_type") && DOUBTFUL,
              )}
            >
              <option value="">Sin determinar</option>
              {DOC_TYPES.map((type) => (
                <option key={type} value={type}>
                  {DOC_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          )}
        </ReviewField>
        {text("supplier_name", "Proveedor", { maxLength: 200, doubtField: "supplier_name" })}
        {text("supplier_tax_id", "NIF del proveedor", { maxLength: 32, doubtField: "supplier_tax_id" })}
        {text("recipient_tax_id", "NIF del destinatario", { maxLength: 32, doubtField: "recipient_tax_id" })}
        {text("invoice_number", "Número de factura", { maxLength: 64, doubtField: "invoice_number" })}
        <ReviewField name="issue_date" label="Fecha" error={errors["issue_date"]} doubt={firstDoubt(doubts, "issue_date")}>
          {(control) => (
            <Input {...control} name="issue_date" type="date" defaultValue={values["issue_date"] ?? ""} className={cn(firstDoubt(doubts, "issue_date") && DOUBTFUL)} />
          )}
        </ReviewField>
        <ReviewField name="currency" label="Moneda" error={errors["currency"]} doubt={firstDoubt(doubts, "currency")} hint="Código de 3 letras, por ejemplo EUR.">
          {(control) => (
            <Input {...control} name="currency" defaultValue={values["currency"] ?? ""} maxLength={3} autoComplete="off" className={cn("uppercase", firstDoubt(doubts, "currency") && DOUBTFUL)} />
          )}
        </ReviewField>
      </div>

      <fieldset className="grid gap-3">
        <legend className="mb-1 font-heading text-[1.0625rem] font-bold">Desglose de IVA</legend>
        {firstDoubt(doubts, "tax_breakdown") && firstDoubt(doubts, "tax_breakdown")?.line_index == null ? (
          <p className="flex items-start gap-1.5 text-xs font-semibold text-status-doubt">
            <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
            {DOUBT_FIELD_LABELS["tax_breakdown"]}: {doubtReasonText(firstDoubt(doubts, "tax_breakdown")?.reason ?? "")}
          </p>
        ) : null}
        {lines.map((line, index) => {
          const doubt = firstDoubt(doubts, "tax_breakdown", index);
          const err = (part: "rate" | "base" | "vat") => (lineErrorsVisible ? errors[lineName(index, part)] : undefined);
          return (
            <div key={index} role="group" aria-label={`Línea de IVA ${index + 1}`} className={cn("grid gap-3 rounded-md border border-rule p-3", doubt && "border-status-doubt-line")}>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] font-semibold text-ink-soft">Línea {index + 1}</p>
                {lines.length > 1 ? (
                  <Button type="button" variant="ghost" size="icon-sm" aria-label={`Quitar la línea ${index + 1}`} onClick={() => structure((current) => current.filter((_, i) => i !== index))}>
                    <X aria-hidden="true" />
                  </Button>
                ) : null}
              </div>
              {doubt ? <DoubtNote id={`review-line-${index}-doubt`} doubt={doubt} /> : null}
              <div className="grid gap-3 sm:grid-cols-3">
                <ReviewField name={lineName(index, "rate")} label="Tipo de IVA (%)" error={err("rate")}>
                  {(control) => (
                    <Input {...control} name={lineName(index, "rate")} value={line.rate} onChange={(e) => change(index, "rate", e.target.value)} inputMode="decimal" autoComplete="off" placeholder="Ej.: 21" className={cn(AMOUNT, doubt && DOUBTFUL)} />
                  )}
                </ReviewField>
                <ReviewField name={lineName(index, "base")} label="Base imponible (€)" error={err("base")}>
                  {(control) => (
                    <Input {...control} name={lineName(index, "base")} value={line.base} onChange={(e) => change(index, "base", e.target.value)} inputMode="decimal" autoComplete="off" placeholder="Ej.: 1.234,50" className={cn(AMOUNT, doubt && DOUBTFUL)} />
                  )}
                </ReviewField>
                <ReviewField name={lineName(index, "vat")} label="Cuota de IVA (€)" error={err("vat")}>
                  {(control) => (
                    <Input {...control} name={lineName(index, "vat")} value={line.vat} onChange={(e) => change(index, "vat", e.target.value)} inputMode="decimal" autoComplete="off" placeholder="Ej.: 1.234,50" className={cn(AMOUNT, doubt && DOUBTFUL)} />
                  )}
                </ReviewField>
              </div>
            </div>
          );
        })}
        <input type="hidden" name="line_count" value={lines.length} />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            id="review-add-line"
            type="button"
            variant="outline"
            size="sm"
            disabled={lines.length >= MAX_LINES}
            onClick={() => structure((current) => [...current, { rate: "", base: "", vat: "" }])}
          >
            <Plus aria-hidden="true" />
            Añadir línea
          </Button>
          {errors["line_count"] ? <p className="text-[13px] font-semibold text-status-error">{errors["line_count"]}</p> : null}
        </div>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className="mb-1 font-heading text-[1.0625rem] font-bold">Retención y total</legend>
        {firstDoubt(doubts, "withholding") ? <DoubtNote id="review-withholding-doubt" doubt={firstDoubt(doubts, "withholding") as Doubt} /> : null}
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(190px,1fr))]">
          <ReviewField name="withholding_rate" label="Retención IRPF (%)" error={errors["withholding_rate"]} hint="Déjalo vacío si no hay retención.">
            {(control) => <Input {...control} name="withholding_rate" defaultValue={values["withholding_rate"] ?? ""} inputMode="decimal" autoComplete="off" placeholder="Ej.: 15" className={AMOUNT} />}
          </ReviewField>
          {amount("withholding_amount", "Importe retenido (€)")}
          {amount("total", "Total (€)", "total")}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-start gap-3 border-t border-rule pt-5">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Guardar cambios"}
        </Button>
        {actions}
      </div>
    </form>
  );
}
