"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { completeLogo, getLogoUrl, removeLogo, reserveLogo } from "@/lib/profile-actions";
import { ACCEPT_LOGO, logoProblem } from "@/lib/profile-form";
import { NETWORK_MESSAGE, putToStorage } from "@/lib/upload-flow";

type Busy = "idle" | "uploading" | "removing";

/**
 * Logo del negocio (D-01): PNG, JPEG o WebP de hasta 1 MiB. Se comprueba el tipo y el tamaño ANTES de subir (Storage respondería 413 o 415 al
 * `PUT`, sin un texto útil); el archivo va directo del navegador a Storage con la URL firmada y después el servidor lo verifica. Se enseña
 * solo con `<img>` y una URL firmada de 60 s, que se pide al montar, tras cada cambio y una vez más si caduca con la pestaña abierta.
 */
export function LogoPanel({ hasLogo }: { hasLogo: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const [busy, setBusy] = useState<Busy>("idle");
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const retried = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    if (!hasLogo) return; // sin logo no se enseña ninguna URL (el JSX mira `hasLogo`), así que no hace falta vaciarla aquí
    void getLogoUrl().then((signed) => {
      if (alive) setUrl(signed);
    });
    return () => {
      alive = false;
    };
  }, [hasLogo, nonce]);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setMessage(null);
    const problem = logoProblem(file);
    if (problem) {
      setMessage({ tone: "error", text: problem });
      if (fileInput.current) fileInput.current.value = "";
      return;
    }
    setBusy("uploading");
    try {
      const reserved = await reserveLogo({ mimeType: file.type, sizeBytes: file.size });
      if (!reserved.ok) {
        setMessage({ tone: "error", text: reserved.message });
        return;
      }
      const put = await putToStorage(fetch, reserved.upload, file);
      if (!put.ok) {
        setMessage({ tone: "error", text: "No se pudo subir el logo. Comprueba tu conexión e inténtalo de nuevo." });
        return;
      }
      const done = await completeLogo(reserved.id);
      if (!done.ok) {
        setMessage({ tone: "error", text: done.message });
        return;
      }
      retried.current = false;
      setNonce((n) => n + 1);
      setMessage({ tone: "ok", text: "Logo guardado." });
    } catch {
      setMessage({ tone: "error", text: NETWORK_MESSAGE });
    } finally {
      setBusy("idle");
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onRemove() {
    setMessage(null);
    setBusy("removing");
    try {
      const done = await removeLogo();
      setMessage(done.ok ? { tone: "ok", text: "Logo quitado." } : { tone: "error", text: done.message });
      if (done.ok) setUrl(null);
    } catch {
      setMessage({ tone: "error", text: NETWORK_MESSAGE });
    } finally {
      setBusy("idle");
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="grid h-24 w-40 place-items-center overflow-hidden rounded-md border border-rule bg-white text-center text-[13px] text-ink-soft">
          {hasLogo && url ? (
            // eslint-disable-next-line @next/next/no-img-element -- URL firmada de 60 s de Storage: no pasa por el optimizador de imágenes.
            <img
              src={url}
              alt="Logo de tu negocio"
              className="max-h-full max-w-full object-contain"
              onError={() => {
                if (retried.current) return;
                retried.current = true;
                setNonce((n) => n + 1);
              }}
            />
          ) : (
            <span className="px-2">{hasLogo ? "Cargando el logo…" : "Sin logo"}</span>
          )}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="perfil-logo" className="text-[13px] font-semibold text-ink-soft">
            {hasLogo ? "Cambiar el logo" : "Elegir un logo"}
          </Label>
          <Input
            ref={fileInput}
            id="perfil-logo"
            type="file"
            accept={ACCEPT_LOGO}
            disabled={busy !== "idle"}
            aria-describedby="perfil-logo-hint"
            onChange={(event) => void onFile(event.target.files?.[0])}
            className="h-auto max-w-xs py-1.5"
          />
          <p id="perfil-logo-hint" className="text-xs text-ink-soft">
            PNG, JPEG o WebP de hasta 1 MiB.
          </p>
        </div>
        {hasLogo ? (
          <Button type="button" variant="outline" disabled={busy !== "idle"} onClick={() => void onRemove()}>
            {busy === "removing" ? "Quitando…" : "Quitar logo"}
          </Button>
        ) : null}
      </div>
      <p aria-live="polite" className={`min-h-5 text-sm font-semibold ${message?.tone === "error" ? "text-status-error" : "text-status-ok"}`}>
        {busy === "uploading" ? "Subiendo el logo…" : (message?.text ?? "")}
      </p>
    </div>
  );
}
