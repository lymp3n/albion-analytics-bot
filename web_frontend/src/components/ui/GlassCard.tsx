import { PropsWithChildren } from "react";

export function GlassCard({ children }: PropsWithChildren) {
  return (
    <div className="rounded-shell border border-white/15 bg-white/5 p-4 shadow-glass backdrop-blur-xl2">
      {children}
    </div>
  );
}
