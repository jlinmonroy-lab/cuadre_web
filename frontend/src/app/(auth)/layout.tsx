import Link from "next/link";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="main" tabIndex={-1} className="mx-auto grid min-h-dvh w-full max-w-[28rem] content-center gap-6 px-4 py-10">
      <Link href="/" className="font-head text-[2rem] leading-none font-bold text-ink no-underline">
        Cuadre
      </Link>
      {children}
    </main>
  );
}
