// Cliente tipado de la API (openapi-fetch + tipos generados). Añade el Bearer de la sesión a cada petición.
// El frontend solo habla con la API de cuadre-web; nunca con la base de datos ni con servicios de agentes.
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

export type AccessTokenProvider = () => Promise<string | null> | string | null;

export function createApiClient(baseUrl: string, getAccessToken: AccessTokenProvider) {
  const client = createClient<paths>({ baseUrl, cache: "no-store" });
  const bearer: Middleware = {
    async onRequest({ request }) {
      const token = await getAccessToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  client.use(bearer);
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;
