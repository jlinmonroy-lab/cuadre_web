// Catálogo de países de la ficha de cliente (SPEC-W-006 D-01, §5.5). Puro: lo ejecutan directamente los tests.
//
// Los códigos son los MISMOS que `backend/src/cuadre/clients/countries.py` (un test de paridad lee ese archivo y compara). Aquí solo sirven
// para dos cosas de PRESENTACIÓN: el nombre en español del selector y el rótulo del identificador fiscal. El ámbito (nacional, UE o fuera de
// la UE) y el estado de VIES los calcula el servidor: la interfaz no decide nada fiscal.

const ALL =
  "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ " +
  "BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS " +
  "BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN " +
  "CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE " +
  "EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF " +
  "GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM " +
  "HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM " +
  "JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC " +
  "LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK " +
  "ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA " +
  "NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG " +
  "PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW " +
  "SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS " +
  "ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO " +
  "TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI " +
  "VN VU WF WS YE YT ZA ZM ZW";

const EU =
  "AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK";

/** Los 249 códigos ISO 3166-1 alfa-2 asignados (no `XK`, `XI` ni `EU`, que ICU conoce pero no son ISO). */
export const COUNTRY_CODES: readonly string[] = ALL.split(" ");

/** Los 27 Estados miembros de la UE (España incluida). Solo para el rótulo del identificador: el ámbito lo pone el servidor. */
export const EU_COUNTRY_CODES: ReadonlySet<string> = new Set(EU.split(" "));

export type ClientKind = "business" | "individual";
export const CLIENT_KINDS: readonly { value: ClientKind; label: string }[] = [
  { value: "business", label: "Empresa o profesional" },
  { value: "individual", label: "Particular" },
];

const SPANISH = "es";
let names: Intl.DisplayNames | null = null;

/** El nombre del país en español (`Intl.DisplayNames`); si el motor no lo conoce, el propio código. Las pruebas no comparan nombres entre motores. */
export function countryName(code: string): string {
  names ??= new Intl.DisplayNames([SPANISH], { type: "region" });
  try {
    return names.of(code) ?? code;
  } catch {
    return code;
  }
}

/** Los países ordenados por nombre en español (la ñ después de la n, sin distinguir mayúsculas ni acentos como primer criterio). */
export function sortedCountries(): { code: string; name: string }[] {
  const collator = new Intl.Collator(SPANISH);
  return COUNTRY_CODES.map((code) => ({ code, name: countryName(code) })).sort((a, b) => collator.compare(a.name, b.name) || a.code.localeCompare(b.code));
}

export type TaxIdLabel = { label: string; hint: string };

/**
 * Cómo se llama el identificador y qué se espera, según el país y el tipo (D-04). Es solo el rótulo: el control lo hace el servidor, que
 * distingue NIF, NIF-IVA y texto libre con el mismo criterio.
 */
export function taxIdLabel(country: string, kind: ClientKind): TaxIdLabel {
  // Sin país elegido todavía no se sabe cómo se llama: se dice y se pide el país primero.
  if (country === "") return { label: "NIF o identificador fiscal", hint: "Elige primero el país." };
  if (country === "ES") {
    return { label: "NIF", hint: kind === "business" ? "NIF, NIE o CIF español. Obligatorio." : "NIF o NIE español. Opcional." };
  }
  if (EU_COUNTRY_CODES.has(country)) {
    return kind === "business"
      ? { label: "NIF-IVA", hint: "Con el prefijo del país, por ejemplo DE123456789. Obligatorio. Se comprueba en VIES (simulado)." }
      : { label: "Identificador fiscal", hint: "Opcional." };
  }
  return { label: "Identificador fiscal", hint: kind === "business" ? "Letras, números y guiones, hasta 32 caracteres. Obligatorio." : "Opcional." };
}
