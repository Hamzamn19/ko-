"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  {
    label: "Dashboard",
    href: "/",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
        <path
          d="M4 4h7v9H4V4zm9 0h7v5h-7V4zm0 7h7v9h-7v-9zM4 15h7v5H4v-5z"
          fill="currentColor"
        />
      </svg>
    ),
  },
  {
    label: "Cover Generator",
    href: "/cover-generator",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
        <path
          d="M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 1.5V8h3.5L13 4.5z"
          fill="currentColor"
        />
        <path d="M8 12h8M8 16h8" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    label: "Scanner",
    href: "/scanner",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
        <path
          d="M7 3h10v2H7V3zm-2 4h14v6H5V7zm0 8h14v6H5v-6z"
          fill="currentColor"
        />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex lg:flex-col lg:fixed lg:left-0 lg:top-0 lg:h-screen lg:w-[88px] lg:border-r lg:border-border lg:bg-[var(--sidebar)] lg:px-3 lg:py-4">
      <div className="flex h-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        <span className="text-base font-semibold">A</span>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex h-12 items-center justify-center rounded-2xl border transition-all ${
                isActive
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-transparent text-muted-foreground hover:border-border hover:bg-muted"
              }`}
              aria-current={isActive ? "page" : undefined}
              title={item.label}
            >
              <span className="flex items-center justify-center">{item.icon}</span>
            </Link>
          );
        })}
      </nav>
      <div className="flex flex-col gap-2">
        <button
          type="button"
          className="flex h-11 items-center justify-center rounded-2xl border border-transparent text-muted-foreground transition hover:border-border hover:bg-muted"
          title="Settings"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
            <path
              d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zm8.5 3.5c0-.4-.03-.8-.1-1.2l-2.1-.4a6.7 6.7 0 0 0-.9-1.6l1.2-1.8a8.4 8.4 0 0 0-1.7-1.7l-1.8 1.2c-.5-.35-1-.66-1.6-.9l-.4-2.1A8.8 8.8 0 0 0 12 3.5c-.4 0-.8.03-1.2.1l-.4 2.1c-.6.24-1.1.55-1.6.9L6.9 5.4a8.4 8.4 0 0 0-1.7 1.7l1.2 1.8c-.35.5-.66 1-.9 1.6l-2.1.4c-.07.4-.1.8-.1 1.2 0 .4.03.8.1 1.2l2.1.4c.24.6.55 1.1.9 1.6l-1.2 1.8c.5.64 1.1 1.2 1.7 1.7l1.8-1.2c.5.35 1 .66 1.6.9l.4 2.1c.4.07.8.1 1.2.1.4 0 .8-.03 1.2-.1l.4-2.1c.6-.24 1.1-.55 1.6-.9l1.8 1.2c.64-.5 1.2-1.1 1.7-1.7l-1.2-1.8c.35-.5.66-1 .9-1.6l2.1-.4c.07-.4.1-.8.1-1.2z"
              fill="currentColor"
            />
          </svg>
        </button>
        <button
          type="button"
          className="flex h-11 items-center justify-center rounded-2xl border border-transparent text-muted-foreground transition hover:border-danger/40 hover:bg-[rgba(178,58,58,0.08)] hover:text-danger"
          title="Logout"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
            <path
              d="M16 7V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
            />
            <path
              d="M11 12h9m0 0-3-3m3 3-3 3"
              stroke="currentColor"
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </aside>
  );
}
