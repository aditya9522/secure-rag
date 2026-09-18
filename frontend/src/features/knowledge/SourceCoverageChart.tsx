import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DocumentSummary } from "../../lib/api";

const classifications = ["public", "internal", "confidential", "restricted"];

function label(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function SourceCoverageChart({ documents }: { documents: DocumentSummary[] }) {
  const data = useMemo(() => classifications.map((classification) => ({
    classification: label(classification),
    active: documents.filter((document) => document.classification === classification && document.status === "active").length,
    indexing: documents.filter((document) => document.classification === classification && document.status === "indexing").length,
    failed: documents.filter((document) => document.classification === classification && document.status === "failed").length,
    revoked: documents.filter((document) => document.classification === classification && document.status === "revoked").length,
  })), [documents]);
  const hasData = documents.length > 0;

  return <section className="audit-chart-card source-coverage-chart"><div className="audit-chart-heading"><div><h3>Source access mix</h3><p>See how many sources sit at each classification and indexing state.</p></div><span>{documents.length} total</span></div>{hasData ? <div className="audit-chart-area"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}><CartesianGrid stroke="var(--border)" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="classification" tick={{ fill: "var(--text-soft)", fontSize: 9 }} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={{ fill: "var(--text-faint)", fontSize: 9 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontSize: 10 }} cursor={{ fill: "var(--surface-muted)" }} /><Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ color: "var(--text-soft)", fontSize: 9, paddingBottom: 8 }} /><Bar dataKey="active" name="Active" stackId="status" fill="var(--purple)" radius={[0, 0, 0, 0]} barSize={22} /><Bar dataKey="indexing" name="Indexing" stackId="status" fill="var(--amber)" /><Bar dataKey="failed" name="Failed" stackId="status" fill="#d97772" /><Bar dataKey="revoked" name="Revoked" stackId="status" fill="var(--text-faint)" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <div className="audit-chart-empty">Add a governed source to see its access distribution here.</div>}</section>;
}
