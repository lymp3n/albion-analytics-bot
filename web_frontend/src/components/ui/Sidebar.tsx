import { ReactNode, useState } from "react";

type SidebarProps = {
  children: ReactNode;
};

export function Sidebar({ children }: SidebarProps) {
  const [open, setOpen] = useState(true);
  return (
    <aside className="rounded-shell border border-white/15 bg-white/5 p-3 shadow-glass backdrop-blur-xl2">
      <button
        className="mb-3 w-full rounded-xl bg-white/10 px-3 py-2 text-left text-sm"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide categories" : "Show categories"}
      </button>
      {open ? children : null}
    </aside>
  );
}
