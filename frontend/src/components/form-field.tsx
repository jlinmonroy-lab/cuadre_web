import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  id: string;
  name: string;
  label: string;
  type?: "text" | "email" | "password";
  autoComplete?: string;
  inputMode?: "email" | "text";
  defaultValue?: string;
  hint?: string;
  error?: string;
};

/** Campo con etiqueta asociada, ayuda y error enlazados por `aria-describedby`. La validación nativa del navegador se apaga
 *  (`noValidate` en el formulario) para que los mensajes sean los nuestros, en español y junto al campo. */
export function FormField({ id, name, label, type = "text", autoComplete, inputMode, defaultValue, hint, error }: Props) {
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id} className="text-[13px] font-semibold text-ink-soft">
        {label}
      </Label>
      <Input
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        inputMode={inputMode}
        defaultValue={defaultValue}
        required
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {hint ? (
        <p id={hintId} className="text-[13px] text-ink-soft">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-[13px] font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
