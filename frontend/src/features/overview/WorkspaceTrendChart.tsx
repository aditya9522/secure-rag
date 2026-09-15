import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ConversationSummary, DocumentSummary, MemberSummary } from "../../lib/api";

type TrendSeries = { label: string; color: "purple" | "blue" | "pink"; values: number[] };

function bucketCounts(items: Array<{ timestamp: string }>, now: number) {
  const week = 7 * 24 * 60 * 60 * 1000;
  return Array.from({ length: 6 }, (_, index) => items.filter((item) => {
    const age = now - new Date(item.timestamp).getTime();
    return age >= (5 - index) * week && age < (6 - index) * week;
  }).length);
}

function weekLabels(now: number) {
  const week = 7 * 24 * 60 * 60 * 1000;
  return Array.from({ length: 6 }, (_, index) => new Date(now - (5 - index) * week).toLocaleDateString(undefined, { month: "short", day: "numeric" }));
}

export function WorkspaceTrendChart({ conversations, documents, members, canManageMembers }: { conversations: ConversationSummary[]; documents: DocumentSummary[]; members: MemberSummary[]; canManageMembers: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 300_000); return () => window.clearInterval(timer); }, []);

  const series = useMemo<TrendSeries[]>(() => [
    { label: "Sources", color: "purple", values: bucketCounts(documents.map((item) => ({ timestamp: item.created_at })), now) },
    { label: "Conversations", color: "blue", values: bucketCounts(conversations.map((item) => ({ timestamp: item.updated_at })), now) },
    ...(canManageMembers ? [{ label: "Members", color: "pink" as const, values: bucketCounts(members.map((item) => ({ timestamp: item.created_at })), now) }] : []),
  ], [canManageMembers, conversations, documents, members, now]);
  const labels = weekLabels(now);
  const chartData = labels.map((label, index) => ({
    name: label,
    sources: series[0]?.values[index] ?? 0,
    conversations: series[1]?.values[index] ?? 0,
    ...(canManageMembers ? { members: series[2]?.values[index] ?? 0 } : {}),
  }));

  return <section className="panel workspace-trend"><div className="workspace-trend-head"><div><div className="eyebrow accent-eyebrow">Workspace analytics</div><h2>Activity trend</h2><p>Weekly activity from the current organization.</p></div><span className="trend-period">Last 6 weeks</span></div><div className="trend-chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 4 }}><CartesianGrid stroke="var(--border)" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="name" tick={{ fill: "var(--text-faint)", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} /><YAxis allowDecimals={false} tick={{ fill: "var(--text-faint)", fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontSize: 11 }} labelStyle={{ color: "var(--text-soft)" }} /><Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ color: "var(--text-soft)", fontSize: 10, paddingBottom: 12 }} /><Line type="monotone" dataKey="sources" name="Sources" stroke="var(--purple)" strokeWidth={2} dot={{ r: 3, fill: "var(--purple)" }} activeDot={{ r: 5 }} /><Line type="monotone" dataKey="conversations" name="Conversations" stroke="#5e9ce6" strokeWidth={2} dot={{ r: 3, fill: "#5e9ce6" }} activeDot={{ r: 5 }} />{canManageMembers && <Line type="monotone" dataKey="members" name="Members" stroke="#df829e" strokeWidth={2} dot={{ r: 3, fill: "#df829e" }} activeDot={{ r: 5 }} />}</LineChart></ResponsiveContainer></div><p className="trend-note">Only records visible to your current role are included.</p></section>;
}
