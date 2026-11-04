import type { Metadata } from "next";
import Link from "next/link";

import { AuthCard } from "@/components/auth/auth-card";
import { SignupForm } from "@/components/auth/forms";

export const metadata: Metadata = { title: "Crear cuenta" };

export default function SignupPage() {
  return (
    <AuthCard title="Crea tu cuenta" lead="Te enviaremos un correo para confirmarla.">
      <SignupForm />
      <p className="text-sm">
        ¿Ya tienes cuenta?{" "}
        <Link href="/login" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          Entrar
        </Link>
      </p>
    </AuthCard>
  );
}
