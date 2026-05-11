import { useState } from "react";
import { SidebarNav } from "../components/navigation/SidebarNav";
import { KpiCard } from "../components/ui/KpiCard";
import { DashboardShell } from "../layouts/DashboardShell";

const economyNav = [
  { id: "overview", label: "Overview" },
  { id: "operations", label: "Operations" },
  { id: "journal", label: "Journal" },
  { id: "armory", label: "Armory" },
  { id: "reports", label: "Reports" },
];

export function EconomyDashboardPage() {
  const [active, setActive] = useState("overview");
  return (
    <DashboardShell
      title="Economy Dashboard"
      subtitle="Shared shell and tokens with Main dashboard"
      sidebar={<SidebarNav items={economyNav} active={active} onSelect={setActive} />}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Cash Balance" value="—" />
        <KpiCard label="Energy Balance" value="—" />
        <KpiCard label="Pending Entries" value="—" />
        <KpiCard label="Open Alerts" value="—" />
      </div>
    </DashboardShell>
  );
}
