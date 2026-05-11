import { PropsWithChildren, ReactNode } from "react";

type DashboardShellProps = PropsWithChildren<{
  sidebar: ReactNode;
  title: string;
  subtitle: string;
}>;

export function DashboardShell({ sidebar, title, subtitle, children }: DashboardShellProps) {
  return (
    <div className="mx-auto min-h-screen w-full max-w-[1560px] p-5">
      <header className="mb-4 rounded-shell border border-white/15 bg-white/5 p-4 backdrop-blur-xl2">
        <h1 className="text-3xl font-medium tracking-tightplus">{title}</h1>
        <p className="mt-1 text-sm text-apple-muted">{subtitle}</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        {sidebar}
        <main>{children}</main>
      </div>
    </div>
  );
}
