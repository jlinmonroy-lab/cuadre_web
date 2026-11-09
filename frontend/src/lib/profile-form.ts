// Formulario del perfil y de las series ↔ cuerpo de la API (SPEC-W-005 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no valida nada fiscal: ni el NIF, ni el IBAN, ni los rangos. Aquí solo se cruza texto con
// el cuerpo (vacío = `null`) y se señalan los datos que no se pueden ni enviar (una fecha que no existe, un número que no es entero).
import type { components } from "@/api/schema";

import type { Problem } from "./problems.ts";

export type ProfileBody = components["schemas"]["ProfileInput"];
export type ProfileValues = Record<string, string>;
export type ProfileErrors = Record<string, string>;
export type ProfileResult = { ok: true; body: ProfileBody } | { ok: false; errors: ProfileErrors };

/** Los campos que edita la persona, en el orden de la pantalla. El régimen de IVA es un dato fijo y no se envía (el servidor lo fija). */
export const PROFILE_FORM_FIELDS = [
  "legal_name",
  "tax_id",
  "fiscal_address",
  "activity",
  "iae_epigraph",
  "activity_start_date",
  "irpf_rate",
  "home_pct",
  "iban",
] as const;

export const DATE_ERROR = "La fecha de alta no es válida.";
export const RETENTION_OPTIONS = [
  { value: "15.00", label: "15 %" },
  { value: "7.00", label: "7 % (reducida)" },
] as const;

/** Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API. */
const code = (n: number) => String.fromCharCode(n);
const CONTROL = new RegExp(
  `[${code(0)}-${code(0x1f)}${code(0x7f)}-${code(0x9f)}${code(0x200b)}-${code(0x200f)}${code(0x2028)}-${code(0x202e)}${code(0x2060)}${code(0xfeff)}]`,
  "g",
);

export function formatIban(iban: string | null | undefined): string {
  const compact = (iban ?? "").replace(/\s+/g, "");
  return compact.replace(/(.{4})/g, "$1 ").trim();
}

type StoredProfile = { [K in (typeof PROFILE_FORM_FIELDS)[number]]?: string | null };

/** Valores con los que se pinta el formulario: lo guardado, con el IBAN agrupado de cuatro en cuatro. */
export function valuesFromProfile(profile: StoredProfile): ProfileValues {
  const values: ProfileValues = {};
  for (const name of PROFILE_FORM_FIELDS) values[name] = profile[name] ?? "";
  values["iban"] = formatIban(profile.iban);
  return values;
}

/** Lee del `FormData` solo los campos conocidos (entrada no confiable: se ignora todo lo demás). */
export function valuesFromProfileForm(get: (name: string) => unknown): ProfileValues {
  const values: ProfileValues = {};
  for (const name of PROFILE_FORM_FIELDS) {
    const value = get(name);
    values[name] = typeof value === "string" ? value : "";
  }
  return values;
}

function realDay(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

const orNull = (value: string | undefined): string | null => {
  const text = (value ?? "").replace(CONTROL, " ").trim();
  return text === "" ? null : text;
};

export function toProfileBody(values: ProfileValues): ProfileResult {
  const start = orNull(values["activity_start_date"]);
  if (start !== null && !realDay(start)) return { ok: false, errors: { activity_start_date: DATE_ERROR } };
  return {
    ok: true,
    body: {
      legal_name: orNull(values["legal_name"]),
      tax_id: orNull(values["tax_id"]),
      fiscal_address: orNull(values["fiscal_address"]),
      activity: orNull(values["activity"]),
      iae_epigraph: orNull(values["iae_epigraph"]),
      activity_start_date: start,
      irpf_rate: orNull(values["irpf_rate"]),
      home_pct: orNull(values["home_pct"]),
      iban: orNull(values["iban"]),
    },
  };
}

/** De un `invalid_profile` a un error por campo (los textos son del servidor). `null` si el problema no es de campos. */
export function fieldErrorsFromProfileProblem(problem: Problem): ProfileErrors | null {
  if (problem.code !== "invalid_profile" || !problem.profileFields) return null;
  const errors: ProfileErrors = {};
  for (const { field, message } of problem.profileFields) errors[field] ??= message;
  return errors;
}

// --- Series ---------------------------------------------------------------------------------------------------------------------

export const SERIES_FIELDS = ["code", "description", "first_number"] as const;
export const FIRST_NUMBER_ERROR = "El número inicial es un entero entre 1 y 999999.";

export type SeriesInput = { code: string; description: string | null; first_number: number | null };
export type SeriesResult = { ok: true; body: SeriesInput } | { ok: false; errors: ProfileErrors };

export function valuesFromSeriesForm(get: (name: string) => unknown): ProfileValues {
  const values: ProfileValues = {};
  for (const name of SERIES_FIELDS) {
    const value = get(name);
    values[name] = typeof value === "string" ? value : "";
  }
  return values;
}

/** El número inicial es lo único que cambia de tipo (texto → entero); lo demás lo decide el servidor, con su texto. */
export function toSeriesBody(values: ProfileValues): SeriesResult {
  const rawNumber = (values["first_number"] ?? "").trim();
  if (rawNumber !== "" && !/^\d{1,7}$/.test(rawNumber)) return { ok: false, errors: { first_number: FIRST_NUMBER_ERROR } };
  return {
    ok: true,
    body: {
      code: (values["code"] ?? "").replace(CONTROL, " ").trim(),
      description: orNull(values["description"]),
      first_number: rawNumber === "" ? null : Number(rawNumber),
    },
  };
}

export function fieldErrorsFromSeriesProblem(problem: Problem): ProfileErrors | null {
  if (problem.code !== "invalid_series" || !problem.field) return null;
  return { [problem.field]: problem.message };
}

// --- Logo -----------------------------------------------------------------------------------------------------------------------

/** Igual que la API (`cuadre.profile.limits`), la CHECK del bucket y su límite: PNG, JPEG o WebP de hasta 1 MiB. SVG no (puede llevar scripts). */
export const LOGO_MAX_BYTES = 1_048_576;
export const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export type LogoType = (typeof LOGO_TYPES)[number];
export const ACCEPT_LOGO = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";

export const LOGO_TYPE_ERROR = "El logo tiene que ser una imagen PNG, JPEG o WebP.";
export const LOGO_SIZE_ERROR = "El logo no puede pesar más de 1 MiB.";

/** Comprobación previa a subir (Storage respondería 413 o 415 al `PUT`, sin un texto útil). `null` si vale. */
export function logoProblem(file: { type: string; size: number }): string | null {
  if (!(LOGO_TYPES as readonly string[]).includes(file.type)) return LOGO_TYPE_ERROR;
  if (file.size < 1) return "El archivo está vacío.";
  if (file.size > LOGO_MAX_BYTES) return LOGO_SIZE_ERROR;
  return null;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** Los ids de series y de subidas son UUID: lo demás ni se envía a la API. */
export const isUuid = (value: unknown): value is string => typeof value === "string" && UUID.test(value);
