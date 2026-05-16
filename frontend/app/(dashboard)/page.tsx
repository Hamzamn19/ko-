import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";

const quickLinks = [
  {
    title: "Start a new cover",
    body: "Define course info, scoring, and exam structure.",
    href: "/cover-generator",
  },
  {
    title: "Scan exam papers",
    body: "Drop PDF or image files to read and grade.",
    href: "/scanner",
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Accredita"
        title="Operations Dashboard"
        subtitle="Monitor the exam pipeline and jump into creation or scanning workflows."
        rightSlot={
          <button
            type="button"
            className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30"
          >
            Create report snapshot
          </button>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active exams" value="6" />
        <StatCard label="Covers generated" value="128" />
        <StatCard label="Pending scans" value="14" tone="warning" />
        <StatCard label="Completed" value="312" tone="success" />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Activity
              </p>
              <h2 className="mt-2 text-xl font-semibold">Latest movements</h2>
            </div>
            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              Today
            </span>
          </div>
          <div className="mt-6 space-y-4">
            {[
              {
                title: "Cover generated for PHY6202",
                meta: "Exam ID PHY6202-9A2F • 12 mins ago",
              },
              {
                title: "20 papers queued for BIL101",
                meta: "Scanner • 48 mins ago",
              },
              {
                title: "Midterm analytics exported",
                meta: "CLO report • 2 hours ago",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="flex items-start gap-3 rounded-2xl border border-border/70 bg-muted/50 px-4 py-3"
              >
                <span className="mt-1 h-2 w-2 rounded-full bg-primary" />
                <div>
                  <p className="text-sm font-medium text-foreground">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.meta}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          {quickLinks.map((link) => (
            <a
              key={link.title}
              href={link.href}
              className="block rounded-3xl border border-border bg-gradient-to-br from-white/80 via-white/60 to-[rgba(239,143,58,0.08)] p-6 shadow-sm transition hover:-translate-y-0.5"
            >
              <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                Quick link
              </p>
              <h3 className="mt-3 text-lg font-semibold text-foreground">
                {link.title}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">{link.body}</p>
              <span className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-primary">
                Open workflow
                <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
                  <path
                    d="M6 12h12m0 0-4-4m4 4-4 4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    fill="none"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
