// Formulario del perfil ↔ API: vacío es null, solo los campos conocidos, el IBAN agrupado al mostrarlo y las comprobaciones previas.
import assert from "node:assert/strict";
import { test } from "node:test";

import { describeProblem } from "./problems.ts";
import {
  LOGO_MAX_BYTES,
  PROFILE_FORM_FIELDS,
  fieldErrorsFromProfileProblem,
  fieldErrorsFromSeriesProblem,
  formatIban,
  logoProblem,
  toProfileBody,
  toSeriesBody,
  valuesFromProfile,
  valuesFromProfileForm,
} from "./profile-form.ts";

const ZERO_WIDTH = String.fromCharCode(0x200b);
const RLO = String.fromCharCode(0x202e);

test("solo se leen los campos conocidos del formulario", () => {
  const data: Record<string, unknown> = { legal_name: "Alicia", logo_path: "otra/ruta.png", vat_regime: "recargo", iban: 5 };
  const values = valuesFromProfileForm((name) => data[name]);
  assert.deepEqual(Object.keys(values), [...PROFILE_FORM_FIELDS]);
  assert.equal(values["legal_name"], "Alicia");
  assert.equal(values["iban"], "");
  assert.equal("logo_path" in values, false);
});

test("un campo vacío o en blanco viaja como null y el resto tal cual, sin validar nada fiscal", () => {
  const result = toProfileBody({ legal_name: "  Alicia  ", tax_id: "12345678z", fiscal_address: "   ", irpf_rate: "7.00", home_pct: "", iban: "es91 2100" });
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.body.legal_name, "Alicia");
  assert.equal(result.body.tax_id, "12345678z");
  assert.equal(result.body.fiscal_address, null);
  assert.equal(result.body.home_pct, null);
  assert.equal(result.body.activity_start_date, null);
  assert.equal(result.body.iban, "es91 2100");
  assert.equal("vat_regime" in result.body, false);
});

test("los caracteres de control y de ancho cero no llegan a la API", () => {
  const result = toProfileBody({ legal_name: `Ali${ZERO_WIDTH}cia${RLO}` });
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal((result.body.legal_name ?? "").includes(ZERO_WIDTH), false);
    assert.equal((result.body.legal_name ?? "").includes(RLO), false);
  }
});

test("una fecha que no existe se señala junto a su campo y no se envía", () => {
  for (const bad of ["2026-02-30", "31/12/2026", "2026-13-01", "ayer"]) {
    assert.deepEqual(toProfileBody({ activity_start_date: bad }), { ok: false, errors: { activity_start_date: "La fecha de alta no es válida." } }, bad);
  }
  assert.equal(toProfileBody({ activity_start_date: "2024-02-29" }).ok, true);
});

test("el IBAN se agrupa de cuatro en cuatro solo al mostrarlo", () => {
  assert.equal(formatIban("ES9121000418450200051332"), "ES91 2100 0418 4502 0005 1332");
  assert.equal(formatIban("es91 2100 0418"), "es91 2100 0418");
  assert.equal(formatIban(null), "");
  assert.equal(valuesFromProfile({ iban: "ES9121000418450200051332", legal_name: null })["iban"], "ES91 2100 0418 4502 0005 1332");
  assert.equal(valuesFromProfile({ legal_name: null })["legal_name"], "");
});

test("los errores de invalid_profile se pintan junto a cada campo, con el primer texto de cada uno", () => {
  const problem = describeProblem({
    status: 422,
    body: {
      code: "invalid_profile",
      detail: "Revisa.",
      fields: [
        { field: "tax_id", message: "El NIF no es válido: revisa el dígito o la letra de control." },
        { field: "tax_id", message: "otro" },
        { field: "iban", message: "El IBAN no es válido: revisa los dígitos de control." },
      ],
    },
  });
  assert.deepEqual(fieldErrorsFromProfileProblem(problem), {
    tax_id: "El NIF no es válido: revisa el dígito o la letra de control.",
    iban: "El IBAN no es válido: revisa los dígitos de control.",
  });
  assert.equal(fieldErrorsFromProfileProblem(describeProblem({ status: 409, body: { code: "series_in_use", detail: "x" } })), null);
});

test("series: el número inicial es lo único que se convierte; el resto lo decide el servidor", () => {
  assert.deepEqual(toSeriesBody({ code: " fac ", description: "", first_number: "100" }), { ok: true, body: { code: "fac", description: null, first_number: 100 } });
  assert.deepEqual(toSeriesBody({ code: "FAC", first_number: "" }), { ok: true, body: { code: "FAC", description: null, first_number: null } });
  for (const bad of ["abc", "1.5", "-1", "1e3", "12345678"]) {
    assert.equal(toSeriesBody({ code: "FAC", first_number: bad }).ok, false, bad);
  }
  const problem = describeProblem({ status: 422, body: { code: "invalid_series", detail: "El código de la serie lleva de 1 a 8 letras.", field: "code" } });
  assert.deepEqual(fieldErrorsFromSeriesProblem(problem), { code: "El código de la serie lleva de 1 a 8 letras." });
  assert.equal(fieldErrorsFromSeriesProblem(describeProblem({ status: 409, body: { code: "series_code_taken", detail: "x" } })), null);
});

test("logo: PNG, JPEG y WebP de hasta 1 MiB; SVG, GIF y el vacío no", () => {
  for (const type of ["image/png", "image/jpeg", "image/webp"]) assert.equal(logoProblem({ type, size: 1000 }), null, type);
  assert.equal(logoProblem({ type: "image/png", size: LOGO_MAX_BYTES }), null);
  assert.equal(logoProblem({ type: "image/png", size: LOGO_MAX_BYTES + 1 }), "El logo no puede pesar más de 1 MiB.");
  for (const type of ["image/svg+xml", "image/gif", "text/plain", ""]) assert.equal(logoProblem({ type, size: 10 }), "El logo tiene que ser una imagen PNG, JPEG o WebP.", type);
  assert.equal(logoProblem({ type: "image/png", size: 0 }), "El archivo está vacío.");
});
