type KpiCardProps = {
  label: string;
  value: string | number;
};

export function KpiCard({ label, value }: KpiCardProps) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-xl2">
      <p className="text-xs uppercase tracking-[0.12em] text-apple-muted">{label}</p>
      <p className="mt-1 text-2xl font-medium tracking-tightplus">{value}</p>
    </div>
  );
}
