import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MemberSummary } from "../../lib/api";

const clearanceLevels = ["public", "internal", "confidential", "restricted"];

function label(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function MemberAccessChart({ members }: { members: MemberSummary[] }) {
  const data = useMemo(() => clearanceLevels.map((classification) => ({
    clearance: label(classification),
    active: members.filter((member) => member.classification_max === classification && member.status === "active").length,
    invited: members.filter((member) => member.classification_max === classification && member.status === "invited").length,
    suspended: members.filter((member) => member.classification_max === classification && member.status === "suspended").length,
  })), [members]);
  const hasData = members.length > 0;

  return <section className="audit-chart-card member-access-chart"><div className="audit-chart-heading"><div><h3>Member clearance mix</h3><p>Check how access is distributed across the organization.</p></div><span>{members.length} total</span></div>{hasData ? <div className="audit-chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}><CartesianGrid stroke="var(--border)" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="clearance" tick={{ fill: "var(--text-soft)", fontSize: 9 }} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={{ fill: "var(--text-faint)", fontSize: 9 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontSize: 10 }} cursor={{ fill: "var(--surface-muted)" }} /><Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ color: "var(--text-soft)", fontSize: 9, paddingBottom: 8 }} /><Bar dataKey="active" name="Active" fill="var(--purple)" radius={[4, 4, 0, 0]} barSize={24} /><Bar dataKey="invited" name="Invited" fill="var(--green)" radius={[4, 4, 0, 0]} barSize={24} /><Bar dataKey="suspended" name="Suspended" fill="var(--amber)" radius={[4, 4, 0, 0]} barSize={24} /></BarChart></ResponsiveContainer></div> : <div className="audit-chart-empty">Invite a member to see clearance distribution here.</div>}</section>;
}
