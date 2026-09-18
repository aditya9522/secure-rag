import { useEffect, useRef, useState } from "react";
import { Check, CircleHelp, LockKeyhole, LogOut, MoreHorizontal, Settings, ShieldCheck, X } from "lucide-react";
import type { NavItem, OrganizationOption, Role, View } from "../../types";

export function Sidebar({ view, items, organization, identity, role, onNavigate, open, onClose, onHelp, onSignOut }: { view: View; items: NavItem[]; organization: OrganizationOption; identity: { name: string; email: string }; role: Role; onNavigate: (view: View) => void; open: boolean; onClose: () => void; onHelp: () => void; onSignOut: () => void }) {
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!profileMenuOpen) return;
    function dismissMenu(event: PointerEvent) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) setProfileMenuOpen(false);
    }
    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setProfileMenuOpen(false);
    }
    document.addEventListener("pointerdown", dismissMenu);
    document.addEventListener("keydown", dismissOnEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissMenu);
      document.removeEventListener("keydown", dismissOnEscape);
    };
  }, [profileMenuOpen]);
  const openSettings = () => { setProfileMenuOpen(false); onNavigate("settings"); };
  const openHelp = () => { setProfileMenuOpen(false); onClose(); onHelp(); };
  const signOut = () => { setProfileMenuOpen(false); onSignOut(); };
  return <>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={onClose} />}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="brand-row"><div className="brand-mark"><ShieldCheck size={19} strokeWidth={2.5} /></div><span className="brand-name">Aegis<span>RAG</span></span><button className="icon-button mobile-close" onClick={onClose} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-card"><div className="workspace-avatar">{organization.initials}</div><div className="workspace-copy"><span className="eyebrow">Workspace</span><strong>{organization.name}</strong></div></div>
      <div className="sidebar-section-label">Workspace</div>
      <nav className="primary-nav" aria-label="Workspace navigation">{items.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${view === id ? "nav-item-active" : ""}`} aria-current={view === id ? "page" : undefined} onClick={() => onNavigate(id)}><Icon size={17} /><span>{label}</span>{id === "audit" && <span className="nav-dot" />}</button>)}</nav>
      <div className="sidebar-section-label admin-label">Administration</div>
      <nav className="primary-nav" aria-label="Administration navigation"><button className={`nav-item ${view === "settings" ? "nav-item-active" : ""}`} aria-current={view === "settings" ? "page" : undefined} onClick={() => onNavigate("settings")}><Settings size={17} /><span>Settings</span></button><button className="nav-item" onClick={() => { onClose(); onHelp(); }}><CircleHelp size={17} /><span>Help center</span></button></nav>
      <div className="sidebar-bottom"><div className="security-mini"><div className="security-icon"><LockKeyhole size={15} /></div><div><strong>Protected workspace</strong><span>RBAC & tenant isolation on</span></div><Check size={15} className="success-icon" /></div><div className="sidebar-profile-wrap" ref={profileMenuRef}><button className="profile-row" type="button" aria-expanded={profileMenuOpen} aria-haspopup="menu" aria-controls="sidebar-profile-menu" onClick={() => setProfileMenuOpen((current) => !current)}><div className="profile-avatar">{identity.name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</div><div className="profile-copy"><strong>{identity.name}</strong><span>{role === "Admin" ? "System admin" : role === "Organization" ? "Organization admin" : "Workspace member"}</span></div><MoreHorizontal size={17} className="muted-icon" /></button>{profileMenuOpen && <div className="dropdown sidebar-profile-menu" id="sidebar-profile-menu" role="menu"><div className="sidebar-profile-menu-head"><strong>{identity.name}</strong><small>{identity.email}</small></div><button role="menuitem" onClick={openSettings}><Settings size={15} /> Account settings</button><button role="menuitem" onClick={openHelp}><CircleHelp size={15} /> Help center</button><button className="dropdown-action" role="menuitem" onClick={signOut}><LogOut size={15} /> Sign out</button></div>}</div></div>
    </aside>
  </>;
}
