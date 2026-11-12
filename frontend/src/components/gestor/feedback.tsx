import type { FormState } from "@/lib/form-state";

/** El resultado de una acción, anunciado a los lectores de pantalla (`aria-live`). El estado inicial no dice nada. */
export function Feedback({ state }: { state: FormState }) {
  return (
    <p aria-live="polite" className={`text-[13px] font-semibold ${state.status === "error" ? "text-status-error" : "text-status-ok"}`}>
      {state.status === "idle" ? "" : (state.message ?? "")}
    </p>
  );
}
