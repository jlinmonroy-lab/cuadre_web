import type { Metadata } from "next";
import { Domine, Public_Sans } from "next/font/google";

import "./globals.css";

// Las fuentes se descargan al compilar y se sirven desde nuestro dominio: el navegador no pide nada a Google (T-14).
const domine = Domine({ variable: "--font-domine", subsets: ["latin"], display: "swap" });
const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "Cuadre", template: "%s · Cuadre" },
  description: "Facturación, contabilidad y borradores de los modelos 303 y 130 para autónomos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Extensiones del navegador (LanguageTool, Grammarly…) añaden atributos a <html> y <body> antes de hidratar; sin esto, React
    // lo señala como error de hidratación. Solo afecta a los atributos de estos dos elementos, no a sus hijos.
    <html lang="es" className={`${domine.variable} ${publicSans.variable}`} suppressHydrationWarning>
      <body className="min-h-dvh" suppressHydrationWarning>
        <a
          href="#main"
          className="sr-only rounded-md bg-ink px-4 py-2 font-semibold text-sheet focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
        >
          Saltar al contenido
        </a>
        {children}
      </body>
    </html>
  );
}
