import type { LucideIcon } from "lucide-react";
import { ArrowUpRight } from "lucide-react";

export function MetricCard({
  label,
  value,
  trend,
  icon: Icon,
  positive = false,
  iconTone = "purple",
}: {
  label: string;
  value: string;
  trend: string;
  icon: LucideIcon;
  positive?: boolean;
  iconTone?: string;
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${iconTone}`}><Icon size={17} /></div>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      <span className={`metric-trend ${positive ? "trend-positive" : ""}`}>
        {positive && <ArrowUpRight size={13} />}
        {trend}
      </span>
    </div>
  );
}
