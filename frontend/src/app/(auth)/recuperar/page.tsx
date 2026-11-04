import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { AuthCard, AuthCardSkeleton, NoticeBox } from "@/components/auth/auth-card";
import { RecoveryForm } from "@/components/auth/forms";
import { noticeFor } from "@/lib/notices";

export const metadata: Metadata = { title: "Recuperar contraseña" };

export default function RecoveryPage(props: PageProps<"/recuperar">) {
  return (
    <Suspense fallback={<AuthCardSkeleton />}>
      <RecoveryContent searchParams={props.searchParams} />
    </Suspense>
  );
}

async function RecoveryContent({ searchParams }: { searchParams: PageProps<"/recuperar">["searchParams"] }) {
  const params = await searchParams;
  return (
    <AuthCard title="Recupera tu contraseña" lead="Escribe tu correo y te enviaremos un enlace para elegir una nueva.">
      <NoticeBox notice={noticeFor(params.aviso)} />
      <RecoveryForm />
      <p className="text-sm">
        <Link href="/login" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Volver a entrar
        </Link>
      </p>
    </AuthCard>
  );
}
