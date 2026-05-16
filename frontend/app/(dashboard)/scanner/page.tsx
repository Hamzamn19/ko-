import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";

export default function ScannerPage() {
  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Scanner"
        title="Paper Intake"
        subtitle="Upload exam sheets in bulk, monitor the queue, and keep the scan pipeline moving."
      />

      <section className="rounded-3xl border border-dashed border-border bg-card p-6">
        <div className="rounded-2xl border border-dashed border-border/80 bg-muted/40 p-10 text-center transition hover:border-primary/50">
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
            Drag files here or click to upload
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            PNG, JPG, JPEG, or PDF. Multi-file supported.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total" value="0" />
        <StatCard label="Waiting" value="0" tone="warning" />
        <StatCard label="Completed" value="0" tone="success" />
        <StatCard label="Errors" value="0" tone="danger" />
      </section>

      <section className="rounded-3xl border border-border bg-card p-8 text-center shadow-sm">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
            <path
              d="M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 1.5V8h3.5L13 4.5z"
              fill="currentColor"
            />
          </svg>
        </div>
        <p className="mt-4 text-sm font-semibold text-foreground">
          No queued documents yet
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Drop files above to start a scan session.
        </p>
      </section>
    </div>
  );
}
