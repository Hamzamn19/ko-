import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";

const sampleRows = [
  {
    id: "20250101",
    name: "Aylin Demir",
    program: "ENG",
    seat: "A-12",
  },
  {
    id: "20250102",
    name: "Bora Yilmaz",
    program: "CS",
    seat: "B-03",
  },
  {
    id: "20250103",
    name: "Ceren Kaya",
    program: "ME",
    seat: "A-15",
  },
];

export default function AttendanceListPage() {
  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Cover Generator"
        title="Attendance List"
        subtitle="Upload the attendance file or edit entries before generating covers."
        rightSlot={
          <button
            type="button"
            className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30"
          >
            Export template
          </button>
        }
      />

      <section className="rounded-3xl border border-dashed border-border bg-card p-6">
        <div className="rounded-2xl border border-dashed border-border/80 bg-muted/40 p-8 text-center transition hover:border-primary/50">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
              <path
                d="M12 3v12m0-12 4 4m-4-4-4 4M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"
                stroke="currentColor"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <p className="mt-4 text-sm font-semibold text-foreground">
            Drop attendance XLSX here
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Or click to browse and map columns.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total students" value="24" />
        <StatCard label="Missing IDs" value="0" tone="success" />
        <StatCard label="Duplicates" value="0" tone="success" />
        <StatCard label="Pending seats" value="4" tone="warning" />
      </section>

      <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Step 3
            </p>
            <h2 className="mt-2 text-lg font-semibold text-foreground">
              Attendance preview
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Review the list before generating covers.
            </p>
          </div>
          <button
            type="button"
            className="rounded-full border border-border bg-muted/40 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground transition hover:border-primary/30 hover:text-primary"
          >
            Add row
          </button>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-border">
          <div className="grid grid-cols-[1.2fr_1.2fr_1fr_1fr] items-center gap-4 border-b border-border bg-muted/50 px-5 py-3 text-xs uppercase tracking-[0.3em] text-muted-foreground">
            <span>Student ID</span>
            <span>Name</span>
            <span>Program</span>
            <span>Seat</span>
          </div>
          <div className="divide-y divide-border">
            {sampleRows.map((row) => (
              <div
                key={row.id}
                className="grid grid-cols-[1.2fr_1.2fr_1fr_1fr] items-center gap-4 px-5 py-3"
              >
                <p className="text-sm font-medium text-foreground">{row.id}</p>
                <p className="text-sm text-foreground">{row.name}</p>
                <p className="text-sm text-muted-foreground">{row.program}</p>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                    {row.seat}
                  </span>
                  <button
                    type="button"
                    className="rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition hover:border-danger/40 hover:text-danger"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            Ready to finalize? Proceed to review and export.
          </p>
          <a
            href="/cover-generator/review"
            className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground transition hover:translate-y-[-1px]"
          >
            Continue to review
          </a>
        </div>
      </section>
    </div>
  );
}
