// Formulario de la ficha de cliente ↔ cuerpo de la API (SPEC-W-006 §5.5).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CLIENT_FORM_FIELDS,
  fieldErrorsFromClientProblem,
  isClientId,
  toClientBody,
  valuesFromClient,
  valuesFromClientForm,
} from "./clients-form.ts";
import { describeProblem } from "./problems.ts";

// Los caracteres raros se construyen con código: la herramienta que escribe este archivo los convertiría en invisibles.
const code = (n: number) => String.fromCharCode(n);

test("los campos del formulario son los de la API, en el orden de la pantalla", () => {
  assert.deepEqual([...CLIENT_FORM_FIELDS], ["name", "kind", "country", "tax_id", "address"]);
});

test("valuesFromClient pinta lo guardado y un campo vacío queda como cadena vacía", () => {
  assert.deepEqual(valuesFromClient({ name: "Estudio Norte S.L.", kind: "business", country: "ES", tax_id: "B00000018", address: null }), {
    name: "Estudio Norte S.L.",
    kind: "business",
    country: "ES",
    tax_id: "B00000018",
    address: "",
  });
  assert.deepEqual(valuesFromClient({}), { name: "", kind: "", country: "", tax_id: "", address: "" });
});

test("valuesFromClientForm lee solo los campos conocidos: el ámbito y el VIES no se envían", () => {
  const form: Record<string, unknown> = {
    name: "Kreativ GmbH",
    kind: "business",
    country: "DE",
    tax_id: "DE534861408",
    address: "Berlín",
    scope: "national",
    vies_status: "valid_simulated",
    archived: "true",
    id: "x",
    owner_id: "y",
  };
  const values = valuesFromClientForm((name) => form[name]);
  assert.deepEqual(Object.keys(values), [...CLIENT_FORM_FIELDS]);
  assert.equal("scope" in values, false);
  assert.equal("vies_status" in values, false);
  // Un archivo, un número o la ausencia de un campo no son texto.
  assert.deepEqual(valuesFromClientForm(() => 5), { name: "", kind: "", country: "", tax_id: "", address: "" });
  assert.deepEqual(valuesFromClientForm(() => new Blob(["x"])), { name: "", kind: "", country: "", tax_id: "", address: "" });
});

test("toClientBody: vacío es null, se recorta y no se valida nada fiscal", () => {
  assert.deepEqual(toClientBody({ name: "  Estudio Norte S.L.  ", kind: "business", country: "ES", tax_id: " b00000018 ", address: "   " }), {
    name: "Estudio Norte S.L.",
    kind: "business",
    country: "ES",
    tax_id: "b00000018", // sin pasar a mayúsculas ni quitar nada: lo normaliza el servidor
    address: null,
  });
  assert.deepEqual(toClientBody({}), { name: null, kind: null, country: null, tax_id: null, address: null });
  // Un NIF mal escrito, un tipo inventado o un país que no existe llegan tal cual: el servidor los rechaza con su texto.
  assert.deepEqual(toClientBody({ name: "X", kind: "otro", country: "zz", tax_id: "12345678A", address: "" }), {
    name: "X",
    kind: "otro",
    country: "zz",
    tax_id: "12345678A",
    address: null,
  });
});

test("toClientBody cambia los controles y los caracteres invisibles por espacios y no los deja pasar", () => {
  const tricky = `Cli${code(0)}ente${code(0x202e)}${code(0x200b)} S.L.${code(0x0a)}`;
  const body = toClientBody({ name: tricky, address: `Calle${code(0x09)}1${code(0xfeff)}` });
  // Cada carácter de control o invisible pasa a ser un espacio (tres seguidos tras «ente»); los del final se recortan.
  assert.equal(body.name, "Cli ente   S.L.");
  assert.equal(body.address, "Calle 1");
  for (const text of [body.name, body.address]) {
    for (const char of text ?? "") assert.ok(char.charCodeAt(0) >= 0x20 && char.charCodeAt(0) !== 0x7f && char.charCodeAt(0) < 0x200b, `carácter ${char.charCodeAt(0)}`);
  }
});

test("un invalid_client del servidor se pinta junto a cada campo, todos a la vez y sin repetir los textos", () => {
  const problem = describeProblem({
    status: 422,
    body: {
      code: "invalid_client",
      detail: "Revisa los campos marcados: no se ha guardado nada.",
      fields: [
        { field: "name", message: "Escribe el nombre del cliente." },
        { field: "country", message: "Elige un país de la lista." },
        { field: "country", message: "segundo error del mismo campo" },
        { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
      ],
    },
  });
  assert.deepEqual(fieldErrorsFromClientProblem(problem), {
    name: "Escribe el nombre del cliente.",
    country: "Elige un país de la lista.",
    tax_id: "El NIF no es válido: revisa el dígito o la letra de control.",
  });
});

test("un client_tax_id_taken se pinta junto al identificador, con el texto del servidor", () => {
  const problem = describeProblem({
    status: 409,
    body: { code: "client_tax_id_taken", detail: "Ya tienes otro cliente activo con ese NIF o identificador fiscal." },
  });
  assert.deepEqual(fieldErrorsFromClientProblem(problem), { tax_id: "Ya tienes otro cliente activo con ese NIF o identificador fiscal." });
});

test("lo que no es un problema de campos no produce errores de campo", () => {
  for (const [status, body] of [
    [409, { code: "client_archived", detail: "Un cliente archivado no se puede editar: reactívalo primero." }],
    [404, { code: "client_not_found", detail: "El cliente no existe." }],
    [422, { code: "invalid_client", detail: "Mal." }], // sin `fields`
    [500, { code: "invalid_client", fields: [{ field: "name", message: "x" }] }],
  ] as const) {
    assert.equal(fieldErrorsFromClientProblem(describeProblem({ status, body })), null, `${status} ${JSON.stringify(body)}`);
  }
});

test("isClientId solo acepta UUID en minúsculas", () => {
  assert.equal(isClientId("0b6e2a9c-3f4d-4e1a-9c7b-5d8a1f2e3c4b"), true);
  for (const other of ["", "x", "0B6E2A9C-3F4D-4E1A-9C7B-5D8A1F2E3C4B", "0b6e2a9c-3f4d-4e1a-9c7b-5d8a1f2e3c4", "../etc", null, undefined, 3, {}]) {
    assert.equal(isClientId(other), false, String(other));
  }
});
