// Fallback de las navegaciones entre apartados (el layout ya está montado; solo cambia la página).
export default function Loading() {
  return (
    <div aria-hidden="true" className="grid gap-4">
      <div className="h-9 w-64 max-w-full rounded bg-muted" />
      <div className="h-32 rounded-panel bg-muted" />
    </div>
  );
}
