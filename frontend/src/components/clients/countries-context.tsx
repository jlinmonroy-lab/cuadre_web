"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

export type CountryOption = { code: string; name: string };

type Countries = { countries: CountryOption[]; nameOf: (code: string) => string };

const CountriesContext = createContext<Countries | null>(null);

/**
 * Los países con su nombre en español, **calculados una sola vez en el servidor** (`sortedCountries()` en la página) y repartidos por contexto.
 * Cada motor nombra distinto algunos códigos (Chromium: FK, HK, MO y PS) y los ordena distinto: si el selector y la lista calcularan los nombres
 * en el navegador, el HTML del servidor y lo que hidrata cada motor no coincidirían (React #418). Con una sola fuente, los dos pintan lo mismo.
 */
export function CountriesProvider({ countries, children }: { countries: CountryOption[]; children: ReactNode }) {
  const value = useMemo<Countries>(() => {
    const names = new Map(countries.map((country) => [country.code, country.name]));
    return { countries, nameOf: (code) => names.get(code) ?? code };
  }, [countries]);
  return <CountriesContext.Provider value={value}>{children}</CountriesContext.Provider>;
}

export function useCountries(): Countries {
  const value = useContext(CountriesContext);
  if (!value) throw new Error("useCountries se usa dentro de CountriesProvider.");
  return value;
}
