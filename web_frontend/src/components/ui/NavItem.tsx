type NavItemProps = {
  label: string;
  active?: boolean;
  onClick?: () => void;
};

export function NavItem({ label, active, onClick }: NavItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
        active ? "bg-apple-blue/30 text-white" : "bg-white/5 text-apple-muted hover:bg-white/10"
      }`}
    >
      {label}
    </button>
  );
}
