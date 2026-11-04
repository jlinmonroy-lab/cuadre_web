"use client";

import Link from "next/link";
import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { login, requestRecovery, resetPassword, signup } from "@/lib/auth-actions";
import { initialFormState, type FormState } from "@/lib/form-state";

const LINK = "font-semibold text-action underline underline-offset-2 hover:text-action-hover";

function SentMessage({ state }: { state: FormState }) {
  return (
    <div role="status" className="grid gap-3 rounded-md border border-status-ok bg-status-ok-bg px-3 py-2.5 text-sm text-status-ok">
      <p className="font-semibold">{state.message}</p>
      <p>
        <Link href="/login" className={LINK}>
          Ir a iniciar sesión
        </Link>
      </p>
    </div>
  );
}

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(login, initialFormState);
  return (
    <form action={action} noValidate className="grid gap-4">
      <ErrorSummary state={state} fieldIds={{ email: "login-email", password: "login-password" }} />
      <input type="hidden" name="next" value={next} />
      <FormField
        id="login-email"
        name="email"
        label="Correo electrónico"
        type="email"
        autoComplete="email"
        inputMode="email"
        defaultValue={state.values?.email}
        error={state.fieldErrors?.email}
      />
      <FormField
        id="login-password"
        name="password"
        label="Contraseña"
        type="password"
        autoComplete="current-password"
        error={state.fieldErrors?.password}
      />
      <Button type="submit" disabled={pending}>
        {pending ? "Entrando…" : "Entrar"}
      </Button>
      <p className="text-sm">
        <Link href="/recuperar" className={LINK}>
          ¿Has olvidado la contraseña?
        </Link>
      </p>
    </form>
  );
}

export function SignupForm() {
  const [state, action, pending] = useActionState(signup, initialFormState);
  if (state.status === "sent") return <SentMessage state={state} />;
  return (
    <form action={action} noValidate className="grid gap-4">
      <ErrorSummary state={state} fieldIds={{ name: "signup-name", email: "signup-email", password: "signup-password" }} />
      <FormField
        id="signup-name"
        name="name"
        label="Nombre"
        autoComplete="name"
        defaultValue={state.values?.name}
        error={state.fieldErrors?.name}
      />
      <FormField
        id="signup-email"
        name="email"
        label="Correo electrónico"
        type="email"
        autoComplete="email"
        inputMode="email"
        defaultValue={state.values?.email}
        error={state.fieldErrors?.email}
      />
      <FormField
        id="signup-password"
        name="password"
        label="Contraseña"
        type="password"
        autoComplete="new-password"
        hint="Al menos 10 caracteres."
        error={state.fieldErrors?.password}
      />
      <Button type="submit" disabled={pending}>
        {pending ? "Creando cuenta…" : "Crear cuenta"}
      </Button>
    </form>
  );
}

export function RecoveryForm() {
  const [state, action, pending] = useActionState(requestRecovery, initialFormState);
  if (state.status === "sent") return <SentMessage state={state} />;
  return (
    <form action={action} noValidate className="grid gap-4">
      <ErrorSummary state={state} fieldIds={{ email: "recovery-email" }} />
      <FormField
        id="recovery-email"
        name="email"
        label="Correo electrónico"
        type="email"
        autoComplete="email"
        inputMode="email"
        defaultValue={state.values?.email}
        error={state.fieldErrors?.email}
      />
      <Button type="submit" disabled={pending}>
        {pending ? "Enviando…" : "Enviar enlace"}
      </Button>
    </form>
  );
}

export function ResetForm() {
  const [state, action, pending] = useActionState(resetPassword, initialFormState);
  return (
    <form action={action} noValidate className="grid gap-4">
      <ErrorSummary state={state} fieldIds={{ password: "reset-password", confirm: "reset-confirm" }} />
      <FormField
        id="reset-password"
        name="password"
        label="Contraseña nueva"
        type="password"
        autoComplete="new-password"
        hint="Al menos 10 caracteres."
        error={state.fieldErrors?.password}
      />
      <FormField
        id="reset-confirm"
        name="confirm"
        label="Repite la contraseña nueva"
        type="password"
        autoComplete="new-password"
        error={state.fieldErrors?.confirm}
      />
      <Button type="submit" disabled={pending}>
        {pending ? "Guardando…" : "Guardar contraseña"}
      </Button>
    </form>
  );
}
