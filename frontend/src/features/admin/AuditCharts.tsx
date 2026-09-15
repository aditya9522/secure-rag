import { useMemo } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AdminMetrics } from "../../lib/api";

interface AuditChartsProps {
  events: Record<string, unknown>[];
  metrics: AdminMetrics | null;
}

interface EventCount {
  event: string;
  count: number;
}

const resourceColors = ["#7357e8", "#5e9ce6", "#df829e"];

function displayEventType(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function eventCounts(events: Record<string, unknown>[]): EventCount[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    const type = String(event.event_type ?? "unknown");
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([event, count]) => ({ event: displayEventType(event), count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 6);
}

function tooltipStyle() {
  return {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text)",
    fontSize: 11,
  };
}

function EventVolumeChart({ events }: { events: Record<string, unknown>[] }) {
  const data = useMemo(() => eventCounts(events), [events]);

  return (
    <section className="audit-chart-card">
      <div className="audit-chart-heading"><div><h3>Policy event volume</h3><p>Recent events grouped by decision type.</p></div><span>{events.length} total</span></div>
      {data.length ? (
        <div className="audit-chart-area">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 12, bottom: 4 }}>
              <XAxis type="number" allowDecimals={false} hide />
              <YAxis type="category" dataKey="event" width={110} tick={{ fill: "var(--text-soft)", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle()} cursor={{ fill: "var(--surface-muted)" }} />
              <Bar dataKey="count" name="Events" fill="#7357e8" radius={[0, 5, 5, 0]} barSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : <div className="audit-chart-empty">Policy activity will appear after authenticated workspace actions.</div>}
    </section>
  );
}

function ResourceDistributionChart({ metrics }: { metrics: AdminMetrics | null }) {
  const data = metrics ? [
    { name: "Organizations", value: metrics.organizations },
    { name: "Users", value: metrics.users },
    { name: "Documents", value: metrics.documents },
  ].filter((item) => item.value > 0) : [];

  return (
    <section className="audit-chart-card">
      <div className="audit-chart-heading"><div><h3>Platform inventory</h3><p>Current resources visible to the platform admin.</p></div><span>{metrics ? "Live" : "Loading"}</span></div>
      {data.length ? (
        <div className="audit-inventory-content">
          <div className="audit-donut">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="82%" paddingAngle={3} stroke="var(--surface)" strokeWidth={3}>
                  {data.map((item, index) => <Cell key={item.name} fill={resourceColors[index % resourceColors.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle()} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="audit-inventory-legend">
            {data.map((item, index) => <div key={item.name}><span style={{ background: resourceColors[index % resourceColors.length] }} /><span>{item.name}</span><strong>{item.value}</strong></div>)}
          </div>
        </div>
      ) : <div className="audit-chart-empty">Inventory data is not available yet.</div>}
    </section>
  );
}

export function AuditCharts({ events, metrics }: AuditChartsProps) {
  return <div className="audit-chart-grid"><EventVolumeChart events={events} /><ResourceDistributionChart metrics={metrics} /></div>;
}
