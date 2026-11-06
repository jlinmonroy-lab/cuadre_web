"use client";

import { Camera, CircleAlert, CircleCheck, FileText, LoaderCircle, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useCallback, useMemo, useReducer, useRef, useState, type ChangeEvent } from "react";

import { buttonVariants, Button } from "@/components/ui/button";
import { discardReservation, reserveUpload } from "@/lib/documents-actions";
import { ACCEPT_FILES, checkFile, formatBytes } from "@/lib/documents";
import { cn } from "@/lib/utils";
import {
  createLimiter,
  newItem,
  putToStorage,
  readViaHandler,
  runUpload,
  type ItemPatch,
  type UploadDeps,
  type UploadItem,
  type UploadSource,
} from "@/lib/upload-flow";

const MAX_AT_ONCE = 3; // lecturas a la vez desde esta pestaña (la API admite 5 por persona)
const MAX_PER_PICK = 20;

type Rejection = { key: string; name: string; message: string };
type State = { items: UploadItem[]; rejected: Rejection[] };
type Action =
  | { type: "add"; items: UploadItem[]; rejected: Rejection[] }
  | { type: "patch"; key: string; patch: ItemPatch }
  | { type: "dismiss"; key: string };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "add":
      return { items: [...state.items, ...action.items], rejected: [...state.rejected, ...action.rejected] };
    case "patch":
      return { ...state, items: state.items.map((item) => (item.key === action.key ? { ...item, ...action.patch } : item)) };
    case "dismiss":
      return { items: state.items.filter((item) => item.key !== action.key), rejected: state.rejected.filter((r) => r.key !== action.key) };
  }
}

const PICKER_FOCUS =
  "cursor-pointer peer-focus-visible/file:outline-2 peer-focus-visible/file:outline-offset-2 peer-focus-visible/file:outline-action peer-focus-visible/camera:outline-2 peer-focus-visible/camera:outline-offset-2 peer-focus-visible/camera:outline-action";

/** Zona de subida: archivos y cámara, con una fila por archivo (cada uno recorre reservar → subir → leer por su cuenta). */
export function UploadPanel() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reducer, { items: [], rejected: [] });
  const files = useRef(new Map<string, File>());
  const counter = useRef(0);
  const [limit] = useState(() => createLimiter(MAX_AT_ONCE));

  const deps = useMemo<UploadDeps>(
    () => ({
      reserve: (input) => reserveUpload(input),
      put: (target, file) => putToStorage((input, init) => fetch(input, init), target, file),
      read: (id) => readViaHandler((input, init) => fetch(input, init), id, "read"),
      discard: (id) => discardReservation(id),
    }),
    [],
  );

  const run = useCallback(
    (item: UploadItem, from: "start" | "reading") => {
      const file = files.current.get(item.key);
      if (!file) return;
      void limit(() => runUpload(deps, item, file, (patch) => dispatch({ type: "patch", key: item.key, patch }), from)).finally(() =>
        startTransition(() => router.refresh()),
      );
    },
    [deps, limit, router],
  );

  function onPick(event: ChangeEvent<HTMLInputElement>, source: UploadSource) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = ""; // para que volver a elegir el mismo archivo dispare otro `change`
    if (picked.length === 0) return;

    const items: UploadItem[] = [];
    const rejected: Rejection[] = [];
    for (const file of picked.slice(0, MAX_PER_PICK)) {
      const key = String(++counter.current);
      const check = checkFile(file);
      if (!check.ok) {
        rejected.push({ key, name: file.name, message: check.message });
        continue;
      }
      files.current.set(key, file);
      items.push(newItem(key, file, check.mimeType, source));
    }
    if (picked.length > MAX_PER_PICK) {
      rejected.push({
        key: String(++counter.current),
        name: "",
        message: `Has elegido ${picked.length} archivos y se suben ${MAX_PER_PICK} de cada vez. Sube el resto en otra tanda.`,
      });
    }
    dispatch({ type: "add", items, rejected });
    for (const item of items) run(item, "start");
  }

  function retry(item: UploadItem) {
    dispatch({ type: "patch", key: item.key, patch: { step: "queued", message: null, retry: null } });
    run({ ...item, step: "queued", message: null, retry: null }, item.retry === "reading" ? "reading" : "start");
  }

  function dismiss(key: string) {
    files.current.delete(key);
    dispatch({ type: "dismiss", key });
  }

  const hasRows = state.items.length > 0 || state.rejected.length > 0;

  return (
    <section aria-labelledby="subir-titulo" className="grid gap-4">
      <div className="grid gap-4 rounded-panel border-2 border-dashed border-rule-strong bg-sheet p-5 sm:grid-cols-[1fr_auto] sm:items-center sm:p-6">
        <div>
          <h2 id="subir-titulo">Sube una factura de compra</h2>
          <p className="mt-1 max-w-[60ch] text-ink-soft">
            Un PDF o una foto (JPG, PNG, HEIC o WebP) de hasta 15 MB. Puedes elegir varios archivos a la vez. En el móvil, «Hacer una foto» abre la cámara.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            id="gastos-archivos"
            type="file"
            multiple
            accept={ACCEPT_FILES}
            onChange={(event) => onPick(event, "file")}
            className="peer/file sr-only"
          />
          <label htmlFor="gastos-archivos" className={cn(buttonVariants(), PICKER_FOCUS)}>
            <Upload aria-hidden="true" />
            Elegir archivos
          </label>
          <input
            id="gastos-camara"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(event) => onPick(event, "camera")}
            className="peer/camera sr-only"
          />
          <label htmlFor="gastos-camara" className={cn(buttonVariants({ variant: "outline" }), PICKER_FOCUS)}>
            <Camera aria-hidden="true" />
            Hacer una foto
          </label>
        </div>
      </div>

      {/* Anuncia los cambios de paso a quien usa un lector de pantalla sin interrumpirle. */}
      <div aria-live="polite" className={hasRows ? "" : "hidden"}>
        <h3 className="sr-only">Subidas en curso</h3>
        <ul className="grid gap-2">
          {state.rejected.map((rejection) => (
            <li key={rejection.key} className="flex items-start justify-between gap-3 rounded-md border border-status-error bg-status-error-bg px-3 py-2.5 text-sm text-status-error">
              <p className="flex min-w-0 items-start gap-2 font-semibold">
                <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                <span className="[overflow-wrap:anywhere]">{rejection.message}</span>
              </p>
              <Button type="button" variant="ghost" size="icon-sm" aria-label="Quitar este aviso" onClick={() => dismiss(rejection.key)}>
                <X aria-hidden="true" />
              </Button>
            </li>
          ))}
          {state.items.map((item) => (
            <UploadRow key={item.key} item={item} onRetry={() => retry(item)} onDismiss={() => dismiss(item.key)} />
          ))}
        </ul>
      </div>
    </section>
  );
}

const STEP_TEXT: Record<string, string> = {
  queued: "En cola",
  reserving: "Preparando la subida…",
  uploading: "Subiendo…",
  reading: "Leyendo…",
};

function UploadRow({ item, onRetry, onDismiss }: { item: UploadItem; onRetry: () => void; onDismiss: () => void }) {
  const finished = item.step === "done" || item.step === "error";
  return (
    <li className="grid gap-1.5 rounded-md border border-rule bg-sheet px-3 py-2.5 text-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="flex min-w-0 items-start gap-2">
          <FileText aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-soft" />
          <span className="min-w-0">
            <span className="block font-semibold [overflow-wrap:anywhere]">{item.name}</span>
            <span className="text-ink-soft">{formatBytes(item.size)}</span>
          </span>
        </p>
        {finished ? (
          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Quitar ${item.name} de la lista`} onClick={onDismiss}>
            <X aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      {item.step === "done" ? <DoneLine item={item} /> : null}
      {item.step === "error" ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <p role="alert" className="flex min-w-0 items-start gap-2 font-semibold text-status-error">
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span className="[overflow-wrap:anywhere]">{item.message}</span>
          </p>
          {item.retry && item.retry !== "none" ? (
            <Button type="button" variant="outline" size="sm" onClick={onRetry}>
              Reintentar
            </Button>
          ) : null}
        </div>
      ) : null}
      {!finished ? (
        <p className="flex items-center gap-2 font-medium text-ink-soft">
          {item.step === "queued" ? null : <LoaderCircle aria-hidden="true" className="size-4 animate-spin motion-reduce:animate-none" />}
          {STEP_TEXT[item.step]}
        </p>
      ) : null}
    </li>
  );
}

function DoneLine({ item }: { item: UploadItem }) {
  const href = item.documentId ? `/gastos/${item.documentId}` : null;
  const text =
    item.result === "review"
      ? "Listo: ya puedes revisarlo."
      : item.result === "extraction_failed"
        ? "No se ha podido leer. Puedes volver a intentarlo o rellenar los datos a mano."
        : item.result === "processing"
          ? "Se está leyendo."
          : "Hecho.";
  const failed = item.result === "extraction_failed";
  return (
    <p className={cn("flex items-start gap-2 font-semibold", failed ? "text-status-doubt" : "text-status-ok")}>
      {failed ? <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" /> : <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />}
      {/* El enlace va dentro del mismo texto: en pantallas estrechas sigue a la frase en vez de caer a otra línea con el icono solo. */}
      <span>
        {text}
        {href ? (
          <>
            {" "}
            <Link href={href} className="text-action underline underline-offset-2 hover:text-action-hover">
              {failed ? "Abrir" : "Revisar"}
            </Link>
          </>
        ) : null}
      </span>
    </p>
  );
}
