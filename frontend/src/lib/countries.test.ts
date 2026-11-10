// Catálogo de países de la ficha de cliente (SPEC-W-006 D-01, §5.5): paridad con el backend, nombres en español y rótulo del identificador.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { CLIENT_KINDS, COUNTRY_CODES, EU_COUNTRY_CODES, countryName, sortedCountries, taxIdLabel } from "./countries.ts";

// La fuente es `cuadre.clients.countries`: este test lee su archivo para que dos listas a mano no se separen sin que falle algo.
const BACKEND = readFileSync(new URL("../../../backend/src/cuadre/clients/countries.py", import.meta.url), "utf8").replaceAll("\r\n", "\n"); // CRLF con autocrlf

function backendCodes(constant: string): string[] {
  const start = BACKEND.indexOf(`${constant} =`);
  assert.ok(start >= 0, `no se encuentra ${constant} en countries.py`);
  const end = BACKEND.indexOf("\n\n", start);
  const block = BACKEND.slice(start, end < 0 ? undefined : end);
  const literals = [...block.matchAll(/"([^"]*)"/g)].map((match) => match[1] ?? "");
  return literals.join(" ").split(" ").filter(Boolean);
}

test("los 249 países son exactamente los del backend", () => {
  const backend = backendCodes("_COUNTRY_CODES");
  assert.equal(backend.length, 249);
  assert.equal(COUNTRY_CODES.length, 249);
  assert.equal(new Set(COUNTRY_CODES).size, 249, "hay códigos repetidos");
  assert.deepEqual([...COUNTRY_CODES].sort(), [...backend].sort());
});

test("los 27 miembros de la UE son exactamente los del backend", () => {
  const backend = backendCodes("_EU_CODES");
  assert.equal(backend.length, 27);
  assert.deepEqual([...EU_COUNTRY_CODES].sort(), [...backend].sort());
  for (const code of EU_COUNTRY_CODES) assert.ok(COUNTRY_CODES.includes(code), `${code} no está en el catálogo`);
});

test("lo que ICU conoce pero no es un ISO asignado no está en el catálogo", () => {
  for (const code of ["XK", "XI", "EU", "UK", "ZZ", "XX", "AN", "SU"]) assert.equal(COUNTRY_CODES.includes(code), false, code);
  for (const code of ["GB", "CH", "ES", "GR"]) assert.equal(COUNTRY_CODES.includes(code), true, code);
  for (const code of ["GB", "CH", "NO", "US", "XK"]) assert.equal(EU_COUNTRY_CODES.has(code), false, code);
});

test("los códigos son dos letras mayúsculas", () => {
  for (const code of COUNTRY_CODES) assert.match(code, /^[A-Z]{2}$/);
});

test("los nombres salen en español y todos los países tienen uno", () => {
  assert.equal(countryName("ES"), "España");
  assert.equal(countryName("DE"), "Alemania");
  assert.equal(countryName("GR"), "Grecia");
  assert.equal(countryName("US"), "Estados Unidos");
  assert.equal(countryName("MX"), "México");
  for (const code of COUNTRY_CODES) {
    const name = countryName(code);
    assert.ok(name.length > 0, code);
    assert.notEqual(name, code, `${code} no tiene nombre en este motor`);
  }
});

test("un código que el motor no entiende vuelve como está, sin romper", () => {
  assert.equal(countryName("!!"), "!!");
  assert.equal(countryName(""), "");
});

test("el selector ordena por nombre en español, con la ñ después de la n", () => {
  const list = sortedCountries();
  assert.equal(list.length, 249);
  assert.equal(new Set(list.map((item) => item.code)).size, 249);
  const collator = new Intl.Collator("es");
  for (let i = 1; i < list.length; i++) {
    const [previous, current] = [list[i - 1], list[i]];
    assert.ok(previous && current && collator.compare(previous.name, current.name) <= 0, `${previous?.name} / ${current?.name}`);
  }
  const names = list.map((item) => item.name);
  assert.ok(names.indexOf("Alemania") < names.indexOf("España"));
  assert.ok(names.indexOf("España") < names.indexOf("Francia"));
  assert.ok(collator.compare("nz", "ña") < 0, "la ñ va después de la n");
});

test("el rótulo del identificador sigue al país y al tipo (D-04)", () => {
  assert.equal(taxIdLabel("ES", "business").label, "NIF");
  assert.equal(taxIdLabel("ES", "individual").label, "NIF");
  assert.equal(taxIdLabel("DE", "business").label, "NIF-IVA");
  assert.equal(taxIdLabel("GR", "business").label, "NIF-IVA");
  assert.equal(taxIdLabel("DE", "individual").label, "Identificador fiscal");
  assert.equal(taxIdLabel("US", "business").label, "Identificador fiscal");
  assert.equal(taxIdLabel("GB", "business").label, "Identificador fiscal"); // GB ya no es de la UE
  assert.equal(taxIdLabel("MX", "individual").label, "Identificador fiscal");
  // Sin país elegido (o con algo que no es un país) no se aventura un rótulo concreto para la UE: solo se pide el país.
  assert.deepEqual(taxIdLabel("", "business"), { label: "NIF o identificador fiscal", hint: "Elige primero el país." });
});

test("la ayuda dice si el identificador es obligatorio", () => {
  assert.match(taxIdLabel("ES", "business").hint, /Obligatorio/);
  assert.match(taxIdLabel("DE", "business").hint, /Obligatorio/);
  assert.match(taxIdLabel("US", "business").hint, /Obligatorio/);
  for (const country of ["ES", "DE", "US"]) assert.match(taxIdLabel(country, "individual").hint, /Opcional/);
  assert.match(taxIdLabel("DE", "business").hint, /VIES \(simulado\)/);
});

test("los tipos de cliente son los de la API y están en español", () => {
  assert.deepEqual(
    CLIENT_KINDS.map((kind) => kind.value),
    ["business", "individual"],
  );
  assert.deepEqual(
    CLIENT_KINDS.map((kind) => kind.label),
    ["Empresa o profesional", "Particular"],
  );
});
