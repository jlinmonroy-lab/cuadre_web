"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type DirtyValue = { dirty: boolean; setDirty: (dirty: boolean) => void };

const DirtyContext = createContext<DirtyValue | null>(null);

/**
 * Comparte entre el formulario de revisión y el panel de comprobaciones si hay cambios SIN GUARDAR (SPEC-W-003 D-02): las comprobaciones
 * son las del servidor sobre lo guardado, así que mientras haya cambios sin guardar no valen y «Registrar gasto» no se puede pulsar.
 * Se monta con una `key` ligada a la lectura: si el formulario se vuelve a montar con datos nuevos, parte limpio.
 */
export function DirtyProvider({ children }: { children: ReactNode }) {
  const [dirty, setDirty] = useState(false);
  const value = useMemo(() => ({ dirty, setDirty }), [dirty]);
  return <DirtyContext value={value}>{children}</DirtyContext>;
}

export function useDirty(): DirtyValue {
  const value = useContext(DirtyContext);
  if (value === null) throw new Error("useDirty se usa dentro de DirtyProvider.");
  return value;
}
