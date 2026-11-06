// Quién es la persona de esta petición. El rol NO sale del JWT: lo devuelve GET /api/me, que lo lee de la base de datos.
import "server-only";

import { redirect } from "next/navigation";
import { connection } from "next/server";
import { cache } from "react";

import type { components } from "@/api/schema";
import { apiFor, sessionToken } from "@/lib/api-server";
import { classifyMeFailure } from "@/lib/me-failure";
import { isRole, type Role } from "@/lib/roles";

export type Me = Omit<components["schemas"]["MeResponse"], "role"> & { role: Role };

/** La API no responde o falla: se muestra «servicio no disponible» (app/error.tsx). Nunca cierra la sesión ni redirige a /login. */
export class ServiceUnavailableError extends Error {
  constructor() {
    super("La API no está disponible");
    this.name = "ServiceUnavailableError";
  }
}

/** Token de acceso de una sesión cuya firma se ha verificado. */
async function accessToken(): Promise<string | null> {
  // La sesión es un dato de la petición (el cliente de Supabase compara la caducidad del token con la hora actual): se declara
  // así de forma explícita para que Next no intente prerenderizar nada que dependa de ella.
  await connection();
  return sessionToken();
}

const problemCode = (body: unknown): string | undefined =>
  typeof body === "object" && body !== null && "code" in body && typeof body.code === "string" ? body.code : undefined;

/** Cierra la sesión por una ruta propia (no se pueden borrar cookies al renderizar) y vuelve a /login con un aviso. */
const signOutAndReturn = (notice: string): never => redirect(`/auth/cerrar?aviso=${notice}`);

export const getMe = cache(async (): Promise<Me> => {
  const token = await accessToken();
  if (!token) redirect("/login");

  const api = apiFor(token);
  let result;
  try {
    result = await api.GET("/api/me");
  } catch {
    throw new ServiceUnavailableError();
  }

  if (result.data) {
    if (!isRole(result.data.role)) throw new ServiceUnavailableError();
    return { ...result.data, role: result.data.role };
  }

  const action = classifyMeFailure({ status: result.response.status, code: problemCode(result.error) });
  switch (action) {
    case "sign-out":
      return signOutAndReturn("sesion");
    case "suspended":
      return signOutAndReturn("suspendida");
    case "profile-missing":
      return signOutAndReturn("perfil");
    case "unavailable":
      throw new ServiceUnavailableError();
  }
});

/** Para una portada o layout de un rol: devuelve la persona o envía a /403. La API y la RLS siguen decidiendo de verdad. */
export async function requireRole(role: Role): Promise<Me> {
  const me = await getMe();
  if (me.role !== role) redirect("/403");
  return me;
}
