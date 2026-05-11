import { useState } from "react";
import { SidebarNav } from "../components/navigation/SidebarNav";
import { KpiCard } from "../components/ui/KpiCard";
import { DashboardShell } from "../layouts/DashboardShell";

const mainNav = [
  { id: "overview", label: "Overview" },
  { id: "players", label: "Players" },
  { id: "tickets", label: "Tickets" },
  { id: "events", label: "Events" },
];

export function MainDashboardPage() {
  const [active, setActive] = useState("overview");
  return (
    <DashboardShell
      title="Main Dashboard"
      subtitle="Apple minimalism shell · preview-first pattern"
      sidebar={<SidebarNav items={mainNav} active={active} onSelect={setActive} />}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Tickets Open" value="—" />
        <KpiCard label="Sessions" value="—" />
        <KpiCard label="Closed Events" value="—" />
        <KpiCard label="System Status" value="—" />
      </div>
    </DashboardShell>
  );
}
