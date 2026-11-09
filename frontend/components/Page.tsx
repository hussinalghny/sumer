"use client";

import Link from "next/link";
import { Controls, Footer } from "./Chrome";
import { Mark } from "./Logo";
import { usePrefs } from "@/lib/prefs";

export function Page({ title, children }: { title: string; children: React.ReactNode }) {
  const { t } = usePrefs();
  return (
    <div className="flex min-h-full flex-col">
      <header className="glass sticky top-0 z-10 border-b border-surface-200 dark:border-night-300">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 py-3">
          <Link href="/" className="flex items-center gap-2 text-xl font-bold"><Mark className="h-8 w-8" />{t.brand}</Link>
          <Controls />
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-14">
        <h1 className="mb-8 text-4xl font-bold tracking-tight sm:text-5xl">{title}</h1>
        <div className="space-y-5 text-lg leading-8 text-ink-soft dark:text-surface-300">{children}</div>
      </main>
      <Footer />
    </div>
  );
}
