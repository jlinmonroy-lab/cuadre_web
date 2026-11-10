// Formulario de la ficha de cliente ↔ cuerpo de la API (SPEC-W-006 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no valida nada fiscal: ni el NIF, ni el NIF-IVA, ni el país, ni el ámbito. Aquí solo se cruza
// texto con el cuerpo (vacío = `null`). El ámbito y el estado de VIES no se envían: los calcula el servidor.
import type { components } from "@/api/schema";

import type { Problem } from "./problems.ts";

export type ClientBody = components["schemas"]["ClientInput"];
export type ClientValues = Record<string, string>;
export type ClientErrors = Record<string, string>;

/** Los campos que edita la persona, en el orden de la pantalla (el mismo en que el servidor enumera los errores). */
export const CLIENT_FORM_FIELDS = ["name", "kind", "country", "tax_id", "address"] as const;

/** Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API. */
const code = (n: number) => String.fromCharCode(n);
const CONTROL = new RegExp(
  `[${code(0)}-${code(0x1f)}${code(0x7f)}-${code(0x9f)}${code(0x200b)}-${code(0x200f)}${code(0x2028)}-${code(0x202e)}${code(0x2060)}${code(0xfeff)}]`,
  "g",
);

type StoredClient = { [K in (typeof CLIENT_FORM_FIELDS)[number]]?: string | null };

/** Valores con los que se pinta el formulario: lo guardado. */
export function valuesFromClient(client: StoredClient): ClientValues {
  const values: ClientValues = {};
  for (const name of CLIENT_FORM_FIELDS) values[name] = client[name] ?? "";
  return values;
}

/** Lee del `FormData` solo los campos conocidos (entrada no confiable: se ignora todo lo demás, también un `scope` o un `vies_status`). */
export function valuesFromClientForm(get: (name: string) => unknown): ClientValues {
  const values: ClientValues = {};
  for (const name of CLIENT_FORM_FIELDS) {
    const value = get(name);
    values[name] = typeof value === "string" ? value : "";
  }
  return values;
}

const orNull = (value: string | undefined): string | null => {
  const text = (value ?? "").replace(CONTROL, " ").trim();
  return text === "" ? null : text;
};

/** El cuerpo de la API: vacío = `null`; el servidor dice qué falta y qué no vale. */
export function toClientBody(values: ClientValues): ClientBody {
  return {
    name: orNull(values["name"]),
    kind: orNull(values["kind"]),
    country: orNull(values["country"]),
    tax_id: orNull(values["tax_id"]),
    address: orNull(values["address"]),
  };
}

/**
 * De un `invalid_client` a un error por campo (los textos son del servidor) y de un `client_tax_id_taken` a un error junto al identificador.
 * `null` si el problema no es de campos.
 */
export function fieldErrorsFromClientProblem(problem: Problem): ClientErrors | null {
  if (problem.code === "client_tax_id_taken") return { tax_id: problem.message };
  if (problem.code !== "invalid_client" || !problem.clientFields) return null;
  const errors: ClientErrors = {};
  for (const { field, message } of problem.clientFields) errors[field] ??= message;
  return errors;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** Los ids de cliente son UUID: lo demás ni se envía a la API. */
export const isClientId = (value: unknown): value is string => typeof value === "string" && UUID.test(value);
