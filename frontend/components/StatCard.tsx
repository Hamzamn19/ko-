type StatCardProps = {
  label: string;
  value: string;
  tone?: "default" | "success" | "warning" | "danger";
};

const toneStyles: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-foreground",
  success: "text-[var(--success)]",
  warning: "text-[var(--warning)]",
  danger: "text-[var(--danger)]",
};

export default function StatCard({ label, value, tone = "default" }: StatCardProps) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
        {label}
      </p>
      <p className={`mt-3 text-2xl font-semibold ${toneStyles[tone]}`}>
        {value}
      </p>
    </div>
  );
}
