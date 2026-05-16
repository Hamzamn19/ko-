"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import PageHeader from "@/components/PageHeader";

export default function QuestionSetupPage() {
  const [rows, setRows] = useState(
    Array.from({ length: 10 }, (_, index) => ({
      id: index + 1,
      points: 10,
    }))
  );

  const totalPoints = useMemo(
    () => rows.reduce((sum, row) => sum + row.points, 0),
    [rows]
  );

  const handlePointsChange = (id: number, value: string) => {
    const parsed = Number(value);
    setRows((current) =>
      current.map((row) =>
        row.id === id
          ? {
              ...row,
              points: Number.isFinite(parsed) ? Math.max(0, parsed) : 0,
            }
          : row
      )
    );
  };

  const handleAddRow = () => {
    setRows((current) => {
      const nextId = current.length
        ? Math.max(...current.map((row) => row.id)) + 1
        : 1;
      return [...current, { id: nextId, points: 10 }];
    });
  };

  const handleRemoveRow = (id: number) => {
    setRows((current) => current.filter((row) => row.id !== id));
  };

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Cover Generator"
        title="Question Setup"
        subtitle="Define the scoring weight for each question before exporting the cover."
      />

      <section className="rounded-3xl border border-border bg-card p-6 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Step 2
            </p>
            <h2 className="mt-2 text-lg font-semibold text-foreground">
              Question scoring grid
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Adjust points per question. Total points should match your target.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              Total: {totalPoints} pts
            </span>
            <button
              type="button"
              onClick={handleAddRow}
              className="rounded-full border border-border bg-muted/40 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground transition hover:border-primary/30 hover:text-primary"
            >
              Add row
            </button>
          </div>
        </div>

        <div className="mt-6 overflow-hidden rounded-2xl border border-border">
          <div className="grid grid-cols-[1fr_140px] items-center gap-4 border-b border-border bg-muted/50 px-5 py-3 text-xs uppercase tracking-[0.3em] text-muted-foreground">
            <span>Question</span>
            <span className="text-right">Points</span>
          </div>
          <div className="divide-y divide-border">
            {rows.map((row) => (
              <div
                key={row.id}
                className="grid grid-cols-[1fr_140px] items-center gap-4 px-5 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                    {row.id}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      Question {row.id}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Written response or MCQ
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveRow(row.id)}
                    className="ml-2 rounded-full border border-border px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground transition hover:border-danger/40 hover:text-danger"
                  >
                    Remove
                  </button>
                </div>
                <input
                  type="number"
                  value={row.points}
                  min={0}
                  onChange={(event) =>
                    handlePointsChange(row.id, event.target.value)
                  }
                  className="h-10 w-full rounded-xl border border-border bg-muted/40 px-3 text-right text-sm font-semibold text-foreground focus:border-primary/40 focus:outline-none"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">
            Tip: Keep totals consistent with the cover sheet default points.
          </p>
          <Link
            href="/cover-generator/attendance-list"
            className="inline-flex items-center justify-center rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground transition hover:translate-y-[-1px]"
          >
            Save and continue
          </Link>
        </div>
      </section>
    </div>
  );
}
