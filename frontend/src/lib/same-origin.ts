// Los Route Handlers de lectura (`POST /gastos/<id>/leer`) autentican con las cookies de sesión. A diferencia de las Server Actions,
// Next no les comprueba el origen: lo hacemos aquí para que una página de otro sitio no pueda disparar una lectura con tu sesión.
// Sin dependencias ni alias: lo ejecutan directamente los tests.

export type OriginHeaders = {
  /** `Sec-Fetch-Site`: lo pone el navegador y la página no puede falsearlo. */
  secFetchSite: string | null;
  origin: string | null;
  /** `X-Forwarded-Host` si lo hay (detrás de un proxy) y, si no, `Host`. */
  host: string | null;
};

export function isSameOrigin({ secFetchSite, origin, host }: OriginHeaders): boolean {
  if (secFetchSite !== null && secFetchSite !== "") return secFetchSite === "same-origin";
  // Navegadores antiguos o clientes que no envían `Sec-Fetch-Site`: se compara el `Origin` con el `Host`.
  if (!origin || !host) return false;
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export function originHeaders(headers: { get(name: string): string | null }): OriginHeaders {
  return {
    secFetchSite: headers.get("sec-fetch-site"),
    origin: headers.get("origin"),
    host: headers.get("x-forwarded-host") ?? headers.get("host"),
  };
}
