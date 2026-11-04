// Validación de los formularios de acceso. Es ayuda de experiencia: Supabase Auth vuelve a validar.
// Los `values` que se devuelven al formulario NUNCA llevan contraseñas: el estado de una Server Action viaja de vuelta al navegador.
// Sin dependencias ni alias: lo ejecutan directamente los tests.

export const PASSWORD_MIN = 10; // T-16, igual que `minimum_password_length` de supabase/config.toml
export const PASSWORD_MAX_BYTES = 72; // bcrypt trunca (y Auth rechaza) lo que pase de 72 bytes, no de 72 caracteres
const EMAIL_MAX = 254;
const NAME_MAX = 80;

export type Validation<V, K extends string> = { values: V; errors: Partial<Record<K, string>> };

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const length = (value: string): number => [...value].length;
const bytes = (value: string): number => new TextEncoder().encode(value).length;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const CONTROL = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/;

function emailError(email: string): string | undefined {
  if (email === "") return "Escribe tu correo.";
  if (email.length > EMAIL_MAX || !EMAIL.test(email)) {
    return email.length > EMAIL_MAX ? "El correo es demasiado largo." : "Escribe un correo válido, por ejemplo nombre@dominio.es.";
  }
  return undefined;
}

function newPasswordError(password: string): string | undefined {
  if (password === "") return "Escribe una contraseña.";
  if (length(password) < PASSWORD_MIN) return `La contraseña debe tener al menos ${PASSWORD_MIN} caracteres.`;
  if (bytes(password) > PASSWORD_MAX_BYTES) {
    return `La contraseña es demasiado larga: el máximo es de ${PASSWORD_MAX_BYTES} bytes (los acentos y símbolos cuentan más de uno).`;
  }
  return undefined;
}

function nameError(name: string): string | undefined {
  if (name === "") return "Escribe tu nombre.";
  if (CONTROL.test(name)) return "El nombre contiene caracteres no válidos.";
  if (length(name) > NAME_MAX) return `El nombre no puede superar los ${NAME_MAX} caracteres.`;
  return undefined;
}

const normalizeEmail = (value: unknown) => text(value).trim().toLowerCase();
const normalizeName = (value: unknown) => text(value).trim().replace(/\s+/g, " ");

function collect<K extends string>(entries: [K, string | undefined][]): Partial<Record<K, string>> {
  const errors: Partial<Record<K, string>> = {};
  for (const [field, message] of entries) if (message !== undefined) errors[field] = message;
  return errors;
}

export function validateSignup(input: { name: unknown; email: unknown; password: unknown }) {
  const name = normalizeName(input.name);
  const email = normalizeEmail(input.email);
  return {
    values: { name, email },
    errors: collect<"name" | "email" | "password">([
      ["name", nameError(name)],
      ["email", emailError(email)],
      ["password", newPasswordError(text(input.password))],
    ]),
  };
}

export function validateLogin(input: { email: unknown; password: unknown }) {
  const email = normalizeEmail(input.email);
  return {
    values: { email },
    errors: collect<"email" | "password">([
      ["email", emailError(email)],
      ["password", text(input.password) === "" ? "Escribe tu contraseña." : undefined],
    ]),
  };
}

export function validateRecovery(input: { email: unknown }) {
  const email = normalizeEmail(input.email);
  return { values: { email }, errors: collect<"email">([["email", emailError(email)]]) };
}

export function validateReset(input: { password: unknown; confirm: unknown }) {
  const password = text(input.password);
  return {
    values: {} as Record<string, never>,
    errors: collect<"password" | "confirm">([
      ["password", newPasswordError(password)],
      ["confirm", text(input.confirm) === password ? undefined : "Las contraseñas no coinciden."],
    ]),
  };
}
