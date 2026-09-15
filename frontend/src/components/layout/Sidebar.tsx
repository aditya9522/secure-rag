import { Check, CircleHelp, LockKeyhole, MoreHorizontal, Settings, ShieldCheck, X } from "lucide-react";
import type { NavItem, OrganizationOption, Role, View } from "../../types";

export function Sidebar({ view, items, organization, identity, role, onNavigate, open, onClose, onHelp }: { view: View; items: NavItem[]; organization: OrganizationOption; identity: { name: string; email: string }; role: Role; onNavigate: (view: View) => void; open: boolean; onClose: () => void; onHelp: () => void }) {
  return <>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="brand-row"><div className="brand-mark"><ShieldCheck size={19} strokeWidth={2.5} /></div><span className="brand-name">Aegis<span>RAG</span></span><button className="icon-button mobile-close" onClick={onClose} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-card"><div className="workspace-avatar">{organization.initials}</div><div className="workspace-copy"><span className="eyebrow">Workspace</span><strong>{organization.name}</strong></div></div>
      <div className="sidebar-section-label">Workspace</div>
      <nav className="primary-nav" aria-label="Workspace navigation">{items.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${view === id ? "nav-item-active" : ""}`} aria-current={view === id ? "page" : undefined} onClick={() => onNavigate(id)}><Icon size={17} /><span>{label}</span>{id === "audit" && <span className="nav-dot" />}</button>)}</nav>
      <div className="sidebar-section-label admin-label">Administration</div>
      <nav className="primary-nav" aria-label="Administration navigation"><button className={`nav-item ${view === "settings" ? "nav-item-active" : ""}`} aria-current={view === "settings" ? "page" : undefined} onClick={() => onNavigate("settings")}><Settings size={17} /><span>Settings</span></button><button className="nav-item" onClick={onHelp}><CircleHelp size={17} /><span>Help center</span></button></nav>
      <div className="sidebar-bottom"><div className="security-mini"><div className="security-icon"><LockKeyhole size={15} /></div><div><strong>Protected workspace</strong><span>RBAC & tenant isolation on</span></div><Check size={15} className="success-icon" /></div><div className="profile-row" role="button" tabIndex={0} onClick={() => onNavigate("settings")} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onNavigate("settings"); }}><div className="profile-avatar">{identity.name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</div><div className="profile-copy"><strong>{identity.name}</strong><span>{role === "Admin" ? "System admin" : role === "Organization" ? "Organization admin" : "Workspace member"}</span></div><MoreHorizontal size={17} className="muted-icon" /></div></div>
    </aside>
  </>;
}
