import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthCard, AuthCardSkeleton, NoticeBox } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/forms";
import { noticeFor } from "@/lib/notices";
import { safeNext } from "@/lib/safe-next";

export const metadata: Metadata = { title: "Entrar" };

export default function LoginPage(props: PageProps<"/login">) {
  return (
    <Suspense fallback={<AuthCardSkeleton />}>
      <LoginContent searchParams={props.searchParams} />
    </Suspense>
  );
}

// `searchParams` es un dato de la petición: se lee dentro de Suspense para que el resto de la página siga siendo estático.
async function LoginContent({ searchParams }: { searchParams: PageProps<"/login">["searchParams"] }) {
  const params = await searchParams;
  return (
    <AuthCard title="Entra en Cuadre">
      <NoticeBox notice={noticeFor(params.aviso)} />
      <LoginForm next={safeNext(params.next, "/")} />
      <p className="text-sm">
        ¿No tienes cuenta?{" "}
        <Link href="/registro" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Crear cuenta
        </Link>
      </p>
    </AuthCard>
  );
}
