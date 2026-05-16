type PageHeaderProps = {
  eyebrow: string;
  title: string;
  subtitle?: string;
  rightSlot?: React.ReactNode;
};

export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  rightSlot,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-primary/70">
          {eyebrow}
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-foreground">
          <span className="font-[var(--font-merriweather)] text-[2rem]">
            {title}
          </span>
        </h1>
        {subtitle ? (
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {subtitle}
          </p>
        ) : null}
      </div>
      {rightSlot ? <div>{rightSlot}</div> : null}
    </div>
  );
}
