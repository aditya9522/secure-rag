import { useEffect, useRef, useState } from "react";
import { Activity, Check, ChevronDown, ChevronRight, LogOut, Menu, Moon, Sun } from "lucide-react";
import type { OrganizationOption, Role, Theme } from "../../types";
import { listNotifications, type NotificationResponse } from "../../lib/api";

export function Header({ organization, organizations, identity, signedIn, onOrganizationChange, theme, onToggleTheme, role, actualRole, onRoleChange, onOpenMenu, onSignOut }: { organization: OrganizationOption; organizations: OrganizationOption[]; identity?: { name: string; email: string }; signedIn: boolean; onOrganizationChange: (organization: OrganizationOption) => void; theme: Theme; onToggleTheme: () => void; role: Role; actualRole: Role; onRoleChange: (role: Role) => void; onOpenMenu: () => void; onSignOut: () => void }) {
  const [openMenu, setOpenMenu] = useState<"organization" | "notifications" | "profile" | null>(null);
  const menuSurfaceRef = useRef<HTMLDivElement>(null);
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [notificationError, setNotificationError] = useState("");
  const previewRoles: Role[] = actualRole === "Admin" ? ["Admin", "Organization", "User"] : actualRole === "Organization" ? ["Organization", "User"] : ["User"];
  useEffect(() => {
    if (!openMenu) return;
    function dismissMenu(event: PointerEvent) {
      if (menuSurfaceRef.current && !menuSurfaceRef.current.contains(event.target as Node)) setOpenMenu(null);
    }
    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenMenu(null);
    }
    document.addEventListener("pointerdown", dismissMenu);
    document.addEventListener("keydown", dismissOnEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissMenu);
      document.removeEventListener("keydown", dismissOnEscape);
    };
  }, [openMenu]);
  async function refreshNotifications() {
    try { setNotifications(await listNotifications(10)); setNotificationError(""); }
    catch (error) { setNotifications([]); setNotificationError(error instanceof Error ? error.message : "Could not load notifications."); }
  }
  useEffect(() => {
    let active = true;
    if (!signedIn) {
      return () => { active = false; };
    }
    void listNotifications(10).then((items) => { if (active) { setNotifications(items); setNotificationError(""); } }).catch((error) => { if (active) { setNotifications([]); setNotificationError(error instanceof Error ? error.message : "Could not load notifications."); } });
    return () => { active = false; };
  }, [signedIn, organization.id]);
  return <header className="topbar"><button className="icon-button menu-button" onClick={onOpenMenu} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{organization.name}</strong></div><div className="topbar-actions" ref={menuSurfaceRef}>
    <div className="org-switcher-wrap"><button className="org-switcher" onClick={() => setOpenMenu(openMenu === "organization" ? null : "organization")} aria-expanded={openMenu === "organization"} aria-haspopup="menu" aria-controls="organization-menu"><span className={`org-dot ${organization.color}`} /><span>{organization.name}</span><ChevronDown size={14} /></button>{openMenu === "organization" && <div className="dropdown org-dropdown" id="organization-menu" role="menu">{organizations.map((org) => <button key={org.id ?? org.name} role="menuitem" onClick={() => { onOrganizationChange(org); setOpenMenu(null); }}><span className={`org-dot ${org.color}`} /><span><strong>{org.name}</strong><small>{org.detail}</small></span>{org.name === organization.name && <Check size={15} />}</button>)}</div>}</div>
    <button className="icon-button" onClick={() => { setOpenMenu(null); onToggleTheme(); }} aria-label="Toggle theme" title="Toggle theme">{theme === "light" ? <Moon size={18} /> : <Sun size={18} />}</button><div className="notification-wrap"><button className="icon-button notification-button" onClick={() => { const opening = openMenu !== "notifications"; setOpenMenu(opening ? "notifications" : null); if (opening) void refreshNotifications(); }} aria-label="Notifications" aria-expanded={openMenu === "notifications"} aria-haspopup="dialog" aria-controls="notification-menu"><span className={`notification-dot ${notifications.length ? "" : "notification-dot-hidden"}`} /><Activity size={18} /></button>{openMenu === "notifications" && <div className="dropdown notification-dropdown" id="notification-menu" role="status"><div className="notification-head"><strong>Notifications</strong><small>{notificationError ? "Unavailable" : notifications.length ? `${notifications.length} recent` : "All caught up"}</small></div>{notificationError ? <div className="notification-empty">{notificationError}</div> : notifications.length ? notifications.map((notification) => <div className="notification-item" key={notification.id}><span className={`notification-status ${notification.severity}`} /><div><strong>{notification.title}</strong><small>{notification.detail}</small><time>{new Date(notification.created_at).toLocaleString()}</time></div></div>) : <div className="notification-empty">Workspace activity will appear here.</div>}</div>}</div>
    <div className="profile-menu-wrap"><button className="top-profile" onClick={() => setOpenMenu(openMenu === "profile" ? null : "profile")} aria-expanded={openMenu === "profile"} aria-haspopup="dialog" aria-controls="profile-menu"><span className="profile-avatar small">{identity?.name.split(" ").map((part) => part[0]).join("").slice(0, 2) || "JD"}</span><ChevronDown size={14} /></button>{openMenu === "profile" && <div className="dropdown profile-dropdown" id="profile-menu" role="dialog" aria-label="Profile menu"><div className="profile-dropdown-head"><span className="profile-avatar">{identity?.name.split(" ").map((part) => part[0]).join("").slice(0, 2) || "JD"}</span><div><strong>{identity?.name || "Signed-in user"}</strong><small>{identity?.email || ""}</small></div></div>{actualRole !== "User" && <div className="role-select"><span>Presentation preview</span><select value={role} onChange={(event) => onRoleChange(event.target.value as Role)}>{previewRoles.map((preview) => <option key={preview}>{preview}</option>)}</select></div>}<div className="profile-access-note">Access is always enforced by the API.</div>{signedIn && <button className="dropdown-action" onClick={() => { setOpenMenu(null); onSignOut(); }}><LogOut size={15} /> Sign out</button>}</div>}</div>
  </div></header>;
}
