import { expenseBadges, type BadgeTone } from "@/lib/expenses";

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-muted text-ink-soft",
  eu: "bg-scope-eu-bg text-scope-eu",
  doubt: "bg-status-doubt-bg text-status-doubt",
};

type Badged = Parameters<typeof expenseBadges>[0];

/** Las marcas de un gasto («Sin factura», «UE», «IVA no deducible»): siempre texto, el color solo refuerza. */
export function ExpenseBadges({ expense, extra }: { expense: Badged; extra?: { label: string; tone: BadgeTone }[] }) {
  const badges = [...expenseBadges(expense), ...(extra ?? [])];
  if (badges.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Marcas del gasto">
      {badges.map((badge) => (
        <li key={badge.label} className={`rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${TONES[badge.tone]}`}>
          {badge.label}
        </li>
      ))}
    </ul>
  );
}
