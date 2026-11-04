"use server";

// Server Actions de acceso. Todo lo que reciben es entrada no confiable: se valida aquí aunque el formulario ya lo haya hecho.
// Las contraseñas solo se leen del FormData y nunca se devuelven al navegador.
import { redirect } from "next/navigation";

import { loginMessage, recoveryOutcome, resetOutcome, signupOutcome } from "@/lib/auth-errors";
import type { FormState } from "@/lib/form-state";
import { safeNext } from "@/lib/safe-next";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { validateLogin, validateRecovery, validateReset, validateSignup } from "@/lib/validation";

const hasErrors = (errors: object) => Object.keys(errors).length > 0;
const secret = (formData: FormData, name: string): string => {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
};

export async function login(_previous: FormState, formData: FormData): Promise<FormState> {
  const password = secret(formData, "password");
  const { values, errors } = validateLogin({ email: formData.get("email"), password });
  if (hasErrors(errors)) return { status: "error", fieldErrors: errors, values };

  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.signInWithPassword({ email: values.email, password });
  if (error) return { status: "error", message: loginMessage(error), values };

  redirect(safeNext(formData.get("next"), "/"));
}

export async function signup(_previous: FormState, formData: FormData): Promise<FormState> {
  const password = secret(formData, "password");
  const { values, errors } = validateSignup({ name: formData.get("name"), email: formData.get("email"), password });
  if (hasErrors(errors)) return { status: "error", fieldErrors: errors, values };

  const supabase = await createSupabaseServerClient();
  // El nombre viaja en user_metadata solo para el trigger de alta. El rol y el estado NUNCA salen de los metadatos.
  const { error } = await supabase.auth.signUp({ email: values.email, password, options: { data: { display_name: values.name } } });

  const outcome = signupOutcome(error);
  switch (outcome.kind) {
    case "sent":
      return {
        status: "sent",
        message: "Te hemos enviado un correo para confirmar tu cuenta. Abre el enlace que contiene y después inicia sesión.",
      };
    case "field":
      return { status: "error", fieldErrors: { [outcome.field]: outcome.message }, values };
    case "error":
      return { status: "error", message: outcome.message, values };
  }
}

export async function requestRecovery(_previous: FormState, formData: FormData): Promise<FormState> {
  const { values, errors } = validateRecovery({ email: formData.get("email") });
  if (hasErrors(errors)) return { status: "error", fieldErrors: errors, values };

  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.resetPasswordForEmail(values.email);

  const outcome = recoveryOutcome(error);
  if (outcome.kind === "error") return { status: "error", message: outcome.message, values };
  // La misma respuesta exista o no la cuenta.
  return {
    status: "sent",
    message: "Si existe una cuenta con ese correo, te hemos enviado un enlace para elegir una contraseña nueva.",
  };
}

export async function resetPassword(_previous: FormState, formData: FormData): Promise<FormState> {
  const supabase = await createSupabaseServerClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims?.sub) redirect("/recuperar?aviso=enlace");

  const password = secret(formData, "password");
  const { errors } = validateReset({ password, confirm: secret(formData, "confirm") });
  if (hasErrors(errors)) return { status: "error", fieldErrors: errors };

  const outcome = resetOutcome((await supabase.auth.updateUser({ password })).error);
  switch (outcome.kind) {
    case "done":
      // Se cierran todas las sesiones: quien cambia la contraseña vuelve a entrar con la nueva.
      await supabase.auth.signOut();
      return redirect("/login?aviso=restablecida");
    case "expired":
      return redirect("/recuperar?aviso=enlace");
    case "field":
      return { status: "error", fieldErrors: { [outcome.field]: outcome.message } };
    case "error":
      return { status: "error", message: outcome.message };
  }
}

export async function logout(): Promise<void> {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut({ scope: "local" }); // solo esta sesión; las de otros dispositivos siguen
  redirect("/login");
}
