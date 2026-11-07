import type { Metadata } from "next";
import Link from "next/link";

import { NoticeBox } from "@/components/auth/auth-card";
import { AutoRefresh } from "@/components/documents/auto-refresh";
import { DocumentList } from "@/components/documents/document-list";
import { UploadPanel } from "@/components/documents/upload-panel";
import { ExpenseList } from "@/components/expenses/expense-list";
import { buttonVariants } from "@/components/ui/button";
import { listDocuments } from "@/lib/documents-api";
import { cursorParam } from "@/lib/expenses";
import { listExpenses } from "@/lib/expenses-api";
import { noticeFor } from "@/lib/notices";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Gastos" };

export default async function GastosPage(props: PageProps<"/gastos">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const params = await props.searchParams;
  const cursor = cursorParam(params.cursor);
  const [documents, expenses] = await Promise.all([listDocuments(), listExpenses(cursor)]);
  const notice = noticeFor(params.aviso);
  return (
    <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h1>Gastos</h1>
          <p className="mt-1 max-w-[70ch] text-ink-soft">
            Sube una factura de compra y la aplicación lee sus datos. Tú solo revisas lo dudoso antes de registrarla.
          </p>
        </div>
        <Link href="/gastos/nuevo" className={buttonVariants({ variant: "outline" })}>
          Añadir gasto sin factura
        </Link>
      </header>
      <div className="grid gap-6">
        <NoticeBox notice={notice} />
        {/* Next conserva el estado de cliente de esta pantalla al ir a la revisión y volver: tras descartar un documento, la fila «Listo… Revisar»
            de su subida seguiría ahí apuntando a algo que ya no existe. Con un aviso (se llega aquí al descartar) el panel se monta de nuevo;
            los documentos siguen en la lista de abajo, que sale del servidor. */}
        <UploadPanel key={notice ? String(params.aviso) : "sin-aviso"} />
        <section aria-labelledby="documentos-titulo" className="grid gap-3">
          <h2 id="documentos-titulo">Tus documentos</h2>
          <DocumentList documents={documents} />
        </section>
        <section aria-labelledby="registrados-titulo" className="grid gap-3">
          <h2 id="registrados-titulo">Gastos registrados</h2>
          <ExpenseList expenses={expenses.items} />
          {cursor || expenses.next_cursor ? (
            <nav aria-label="Páginas de gastos registrados" className="flex flex-wrap gap-x-6 gap-y-2">
              {cursor ? (
                <Link href="/gastos" className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                  Volver a los más recientes
                </Link>
              ) : null}
              {expenses.next_cursor ? (
                <Link href={`/gastos?cursor=${encodeURIComponent(expenses.next_cursor)}`} className="font-semibold text-action underline underline-offset-2 hover:text-action-hover">
                  Ver más antiguos
                </Link>
              ) : null}
            </nav>
          ) : null}
        </section>
      </div>
      {/* Mientras algo se lee (aquí o en otra pestaña), la lista se actualiza sola. */}
      <AutoRefresh active={documents.some((document) => document.status === "processing")} />
    </>
  );
}
