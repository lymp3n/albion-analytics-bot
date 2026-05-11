import { NavItem } from "../ui/NavItem";
import { Sidebar } from "../ui/Sidebar";

type Item = { id: string; label: string };

type SidebarNavProps = {
  items: Item[];
  active: string;
  onSelect: (id: string) => void;
};

export function SidebarNav({ items, active, onSelect }: SidebarNavProps) {
  return (
    <Sidebar>
      <div className="space-y-2">
        {items.map((item) => (
          <NavItem key={item.id} label={item.label} active={active === item.id} onClick={() => onSelect(item.id)} />
        ))}
      </div>
    </Sidebar>
  );
}
