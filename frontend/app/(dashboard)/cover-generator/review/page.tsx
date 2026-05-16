import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";

const checkpoints = [
  {
    label: "Exam metadata",
    detail: "Course, date, duration",
    status: "Ready",
  },
  {
    label: "Question points",
    detail: "10 questions • 100 points",
    status: "Ready",
  },
  {
    label: "Attendance list",
    detail: "24 students • XLSX mapped",
    status: "Ready",
  },
];

export default function ReviewPage() {
  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Cover Generator"
        title="Review & Generate"
        subtitle="Confirm the summary before exporting the cover package."
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Questions" value="10" />
        <StatCard label="Total points" value="100" tone="success" />
        <StatCard label="Students" value="24" />
        <StatCard label="Generated covers" value="0" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                Step 4
              </p>
              <h2 className="mt-2 text-lg font-semibold text-foreground">
                Final review
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Each section must be ready before export.
              </p>
            </div>
            <span className="rounded-full bg-[rgba(28,124,84,0.12)] px-3 py-1 text-xs text-[var(--success)]">
              All checks passed
            </span>
          </div>

          <div className="mt-6 space-y-3">
            {checkpoints.map((checkpoint) => (
              <div
                key={checkpoint.label}
                className="flex items-center justify-between rounded-2xl border border-border bg-muted/40 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {checkpoint.label}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {checkpoint.detail}
                  </p>
                </div>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">
                  {checkpoint.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl border border-border bg-gradient-to-br from-white/80 via-white/60 to-[rgba(15,93,91,0.12)] p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Output
            </p>
            <h3 className="mt-2 text-lg font-semibold">Export package</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Download cover PDFs and a metadata JSON bundle.
            </p>
            <button
              type="button"
              className="mt-6 w-full rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:translate-y-[-1px]"
            >
              Generate covers
            </button>
          </div>

          <div className="rounded-3xl border border-border bg-card p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Notes
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Export will use the current points grid and attendance list.
            </p>
            <div className="mt-4 rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-xs text-muted-foreground">
              Integrate API call to /api/generate-cover here when backend wiring starts.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
