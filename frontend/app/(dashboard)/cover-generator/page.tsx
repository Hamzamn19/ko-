import Link from "next/link";
import PageHeader from "@/components/PageHeader";

const steps = [
  "Course setup",
  "Question mapping",
  "Attendance list",
  "Review & export",
];

export default function CoverGeneratorPage() {
  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Cover Generator"
        title="Exam Cover Builder"
        subtitle="Define the exam metadata, allocate points, and generate a print-ready cover."
      />

      <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          {steps.map((step, index) => (
            <div key={step} className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-sm font-semibold text-primary">
                {index + 1}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                  Step {index + 1}
                </p>
                <p className="text-sm font-medium text-foreground">{step}</p>
              </div>
              {index < steps.length - 1 ? (
                <div className="hidden h-px w-14 bg-border md:block" />
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                Exam Information
              </p>
              <h2 className="mt-2 text-lg font-semibold text-foreground">
                Configure metadata
              </h2>
            </div>
            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              Required
            </span>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              { label: "Program", placeholder: "Select program" },
              { label: "Course code", placeholder: "Select program first" },
              { label: "Exam type", placeholder: "Midterm" },
              { label: "Mode", placeholder: "Classic (points)" },
              { label: "Exam date", placeholder: "YYYY-MM-DD", type: "date" },
              { label: "Exam time", placeholder: "09:00", type: "time" },
            ].map((field) => (
              <div key={field.label} className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                  {field.label}
                </label>
                <input
                  type={field.type ?? "text"}
                  placeholder={field.placeholder}
                  className="h-11 w-full rounded-2xl border border-border bg-muted/40 px-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none"
                />
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-4">
            {["Duration (min)", "Contribution %", "Questions", "Default points"].map(
              (label) => (
                <div key={label} className="space-y-2">
                  <label className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">
                    {label}
                  </label>
                  <input
                    type="number"
                    className="h-11 w-full rounded-2xl border border-border bg-muted/40 px-4 text-sm text-foreground focus:border-primary/40 focus:outline-none"
                    placeholder="0"
                  />
                </div>
              )
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-3xl border border-border bg-gradient-to-br from-white/70 via-white/50 to-[rgba(15,93,91,0.1)] p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              CLO stream
            </p>
            <h3 className="mt-2 text-lg font-semibold">Select a course</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Course learning outcomes appear here after the course selection.
            </p>
            <div className="mt-6 h-32 rounded-2xl border border-dashed border-border bg-muted/30" />
          </div>

          <div className="rounded-3xl border border-border bg-[rgba(28,124,84,0.08)] p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Total points
            </p>
            <p className="mt-3 text-3xl font-semibold text-[var(--success)]">
              100 / 100
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Ready to proceed
            </p>
            <Link
              href="/cover-generator/question-setup"
              className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:translate-y-[-1px]"
            >
              Continue to question setup
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
