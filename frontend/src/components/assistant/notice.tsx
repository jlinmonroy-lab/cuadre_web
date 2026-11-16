import { NOTICE } from "@/lib/chat";

/** El aviso permanente de que el asistente orienta y no asesora (RES-05, D-09). Visible bajo el campo en todos los estados y repetido en cada abstención. */
export function Notice({ className = "" }: { className?: string }) {
  return (
    <p className={`rounded-r-md border-l-[3px] border-rule-strong bg-[#EEF2EF] px-4 py-2 text-sm text-ink-soft ${className}`}>{NOTICE}</p>
  );
}
