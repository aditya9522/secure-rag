import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Check, ChevronRight, FileText } from "lucide-react";
import type { ReactNode } from "react";

export function QuickAction({ icon: Icon, title, description, onClick }: { icon: LucideIcon; title: string; description: string; onClick: () => void }) {
  return <button className="quick-action" onClick={onClick}><span className="quick-action-icon"><Icon size={17} /></span><span><strong>{title}</strong><small>{description}</small></span><ChevronRight size={16} /></button>;
}

export function ActivityRow({ icon: Icon, color, title, detail, time }: { icon: LucideIcon; color: string; title: string; detail: string; time: string }) {
  return <div className="activity-row"><span className={`activity-icon ${color}`}><Icon size={16} /></span><div><strong>{title}</strong><span>{detail}</span></div><time>{time}</time></div>;
}

export function ContextItem({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="context-item"><Icon size={15} /><span><small>{label}</small><strong>{value}</strong></span></div>;
}

export function SourceRow({ title, type }: { title: string; type: string }) {
  return <div className="source-row"><span className="file-icon"><FileText size={14} /></span><span><strong>{title}</strong><small>{type} · Indexed</small></span><Check size={14} className="success-icon" /></div>;
}

export function HealthRow({ label, detail, value }: { label: string; detail: string; value: string }) {
  return <div className="health-row"><span className="health-dot" /><div><strong>{label}</strong><small>{detail}</small></div><span className="health-value">{value}</span></div>;
}

export function PolicyEvent({ type, detail, time, good = false }: { type: string; detail: string; time: string; good?: boolean }) {
  return <div className="policy-event"><span className={`policy-event-icon ${good ? "good" : ""}`}>{good ? <Check size={14} /> : <AlertTriangle size={14} />}</span><div><strong>{type}</strong><small>{detail}</small></div><time>{time}</time></div>;
}

export function SettingRow({ label, description, children }: { label: string; description: string; children: ReactNode }) {
  return <div className="setting-row"><div><strong>{label}</strong><p>{description}</p></div>{children}</div>;
}
