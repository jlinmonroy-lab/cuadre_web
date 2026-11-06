// ADR-0006, AC-14 · Lectura y formato de importes en la interfaz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { centsToInput, formatCents, parseAmount, parseCents } from "./money.ts";

const ok = (cents: number) => ({ kind: "ok", cents });

test("importes válidos, con las costumbres españolas y las de la calculadora", () => {
  const cases: [string, number][] = [
    ["0", 0],
    ["0,00", 0],
    ["12", 1200],
    ["12,5", 1250],
    ["12,50", 1250],
    ["12.5", 1250],
    ["12.50", 1250],
    ["1234,50", 123450],
    ["1234.50", 123450],
    ["1.234,50", 123450],
    ["12.345.678,90", 1234567890],
    ["007,50", 750],
    ["999999999999,99", 99999999999999], // 12 cifras enteras: el máximo que admite el contrato
    ["-12,50", -1250],
    ["\u221212,50", -1250], // signo menos de Unicode
    ["-0,00", 0],
    ["  12,50  ", 1250],
    ["12,50 €", 1250],
    ["€ 12,50", 1250],
    ["1.234,50\u00a0€", 123450], // lo que escribe Intl
    ["1 234,50", 123450],
  ];
  for (const [text, cents] of cases) assert.deepEqual(parseAmount(text), ok(cents), JSON.stringify(text));
});

test("trampas de coma flotante: el resultado es siempre el entero exacto", () => {
  // En coma flotante 0,29 * 100 = 28,999…; 1,15 * 100 = 114,999…; 4,35 * 100 = 434,999…
  for (const [text, cents] of [["0,29", 29], ["1,15", 115], ["4,35", 435], ["8,20", 820], ["19,99", 1999], ["1.005,05", 100505]] as const) {
    assert.deepEqual(parseAmount(text), ok(cents), text);
  }
});

test("vacío no es lo mismo que no válido", () => {
  for (const blank of ["", "   ", "\t", "\u00a0", "€", " € "]) assert.deepEqual(parseAmount(blank), { kind: "empty" }, JSON.stringify(blank));
  assert.deepEqual(parseAmount(null), { kind: "empty" });
  assert.deepEqual(parseAmount(undefined), { kind: "empty" });
});

test("lo que no se puede leer con seguridad se rechaza en vez de adivinarlo", () => {
  const invalid = [
    "1.200", // ambiguo: ¿1200 o 1,200?
    "1.200.000", // sin coma, los puntos no se interpretan como millares
    "12,345", // tres decimales
    "12,", // coma sin decimales
    ",50", // sin parte entera
    "1,2,3",
    "12,50,",
    "1.2,50", // millares mal agrupados
    "12.50,00",
    "1.2.3",
    "12.345", // tres decimales con punto (y ambiguo)
    "1e3",
    "1E3",
    "NaN",
    "Infinity",
    "0x10",
    "abc",
    "12a",
    "12 3,50 4", // tras quitar espacios: 1234,504 (3 decimales)
    "--12",
    "+12",
    "12-",
    "1,50-",
    "-",
    "-,50",
    "9999999999999,00", // 13 cifras enteras
    "1000000000000",
    "١٢,٥٠", // dígitos arábigo-índicos
    "１２,５０", // dígitos de ancho completo
  ];
  for (const text of invalid) assert.deepEqual(parseAmount(text), { kind: "invalid" }, JSON.stringify(text));
  for (const other of [12.5, 12, true, {}, [], NaN]) assert.deepEqual(parseAmount(other), { kind: "invalid" }, String(other));
});

test("parseCents devuelve null para vacío y para no válido", () => {
  assert.equal(parseCents("1.234,50"), 123450);
  assert.equal(parseCents(""), null);
  assert.equal(parseCents("1.200"), null);
  assert.equal(parseCents(undefined), null);
});

test("-0 nunca sale como resultado", () => {
  assert.ok(Object.is(parseCents("-0"), 0));
  assert.ok(Object.is(parseCents("-0,00"), 0));
});

test("centsToInput: coma decimal, dos decimales y sin agrupar", () => {
  assert.equal(centsToInput(0), "0,00");
  assert.equal(centsToInput(5), "0,05");
  assert.equal(centsToInput(29), "0,29");
  assert.equal(centsToInput(1250), "12,50");
  assert.equal(centsToInput(123450), "1234,50");
  assert.equal(centsToInput(-1250), "-12,50");
  assert.equal(centsToInput(-5), "-0,05");
  assert.equal(centsToInput(99999999999999), "999999999999,99");
  for (const none of [null, undefined, 12.5, NaN, Infinity, 2 ** 60]) assert.equal(centsToInput(none), "", String(none));
});

test("ida y vuelta: lo que se muestra en un campo se vuelve a leer igual", () => {
  const samples = [0, 1, 9, 10, 29, 99, 100, 101, 1250, 123450, 99999999999999, -1, -100, -123450, -99999999999999];
  for (const cents of samples) assert.equal(parseCents(centsToInput(cents)), cents, String(cents));
  // Y un barrido: todos los céntimos de 0 a 2.500 y una muestra de valores grandes.
  for (let cents = -2500; cents <= 2500; cents++) assert.equal(parseCents(centsToInput(cents)), cents, String(cents));
  for (let n = 1; n < 1e12; n *= 7) assert.equal(parseCents(centsToInput(n)), n, String(n));
});

test("formatCents: euros en formato es-ES", () => {
  const clean = (value: string) => value.replaceAll("\u00a0", " ").replaceAll("\u202f", " ");
  assert.equal(clean(formatCents(0)), "0,00 €");
  assert.equal(clean(formatCents(5)), "0,05 €");
  assert.equal(clean(formatCents(1250)), "12,50 €");
  assert.equal(clean(formatCents(123450)), "1234,50 €"); // es-ES no agrupa los números de cuatro cifras
  assert.equal(clean(formatCents(1234567890)), "12.345.678,90 €");
  assert.equal(clean(formatCents(-1250)), "-12,50 €");
  assert.equal(clean(formatCents(29)), "0,29 €");
  assert.equal(clean(formatCents(435)), "4,35 €");
});

test("formatCents sin importe", () => {
  for (const none of [null, undefined, 12.5, NaN]) assert.equal(formatCents(none), "—", String(none));
});
