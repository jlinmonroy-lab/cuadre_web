import * as React from "react";

import { cn } from "@/lib/utils";

/** Un `<select>` nativo con el aspecto de `Input` (las listas cortas de Cuadre no necesitan más, y el nativo es accesible y táctil). */
function NativeSelect({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="native-select"
      className={cn(
        "h-10 w-full min-w-0 rounded-lg border border-input bg-white px-3 text-[15px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}

export { NativeSelect };
