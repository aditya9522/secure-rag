import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, Check, KeyRound, LockKeyhole, Moon, ShieldCheck, SlidersHorizontal, Sun, UserRound, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import toast from "react-hot-toast";
import { getReadiness, listNotifications, updateMe, type NotificationResponse, type OrganizationSummary, type UserSummary } from "../../lib/api";
import type { Role, Theme } from "../../types";
import { PageHeader } from "../../components/ui/PageHeader";
import { SettingRow } from "../../components/ui/Rows";

type SettingsSection = "general" | "security" | "integrations" | "notifications";
type ProfileMessage = { text: string; tone: "success" | "error" } | null;

interface ProfileUpdate {
  user: UserSummary;
  current_organization: OrganizationSummary;
  organizations: OrganizationSummary[];
}

interface SettingsPageProps {
  currentName: string;
  theme: Theme;
  onToggleTheme: () => void;
  role: Role;
  actualRole: Role;
  onRoleChange: (role: Role) => void;
  onProfileUpdated: (profile: ProfileUpdate) => void;
}

function RoleCard({ icon: Icon, title, description, active, onClick }: { icon: LucideIcon; title: Role; description: string; active: boolean; onClick: () => void }) {
  return (
    <button className={`role-card ${active ? "role-card-active" : ""}`} onClick={onClick} type="button">
      <span className="role-card-icon"><Icon size={17} /></span>
      <span><strong>{title}</strong><small>{description}</small></span>
      {active && <Check size={15} className="success-icon" />}
    </button>
  );
}

function SecurityStatus({ icon: Icon, label, description }: { icon: LucideIcon; label: string; description: string }) {
  return (
    <div className="toggle-row">
      <span className="setting-icon"><Icon size={16} /></span>
      <div><strong>{label}</strong><p>{description}</p></div>
      <span className="status-pill status-active"><span />Enforced</span>
    </div>
  );
}

function SettingsNav({ active, onChange }: { active: SettingsSection; onChange: (section: SettingsSection) => void }) {
  const items: Array<[SettingsSection, string, LucideIcon]> = [
    ["general", "General", SlidersHorizontal],
    ["security", "Security & roles", ShieldCheck],
    ["integrations", "Integrations", KeyRound],
    ["notifications", "Notifications", Activity],
  ];

  return (
    <nav className="settings-nav" aria-label="Settings sections">
      {items.map(([id, label, Icon]) => (
        <button key={id} type="button" className={active === id ? "settings-nav-active" : ""} onClick={() => onChange(id)}>
          <Icon size={16} /> {label}
        </button>
      ))}
    </nav>
  );
}

function ProfileSettings({ currentName, onProfileUpdated }: { currentName: string; onProfileUpdated: (profile: ProfileUpdate) => void }) {
  const [name, setName] = useState(currentName);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<ProfileMessage>(null);
  const [saving, setSaving] = useState(false);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      const errorMessage = "Full name cannot be empty.";
      setMessage({ text: errorMessage, tone: "error" });
      toast.error(errorMessage);
      return;
    }

    setMessage(null);
    setSaving(true);
    try {
      const profile = await updateMe({
        full_name: trimmedName,
        current_password: currentPassword || undefined,
        new_password: newPassword || undefined,
      });
      onProfileUpdated(profile);
      setName(profile.user.full_name);
      setCurrentPassword("");
      setNewPassword("");
      setMessage({ text: "Profile settings saved.", tone: "success" });
      toast.success("Profile settings saved.");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Could not save profile settings.";
      setMessage({ text: errorMessage, tone: "error" });
      toast.error(errorMessage);
    } finally {
      setSaving(false);
    }
  }

  const unchanged = name.trim() === currentName.trim() && !newPassword;

  return (
    <section className="panel settings-section">
      <div className="settings-section-head">
        <div><h2>Profile</h2><p>Update your name or change your password for this account.</p></div>
      </div>
      <form className="profile-form" onSubmit={saveProfile}>
        <label htmlFor="profile-full-name">Full name
          <input id="profile-full-name" value={name} onChange={(event) => setName(event.target.value)} minLength={2} required autoComplete="name" />
        </label>
        <label htmlFor="profile-current-password">Current password
          <input id="profile-current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required={Boolean(newPassword)} />
        </label>
        <label htmlFor="profile-new-password">New password
          <input id="profile-new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength={12} autoComplete="new-password" />
          <small>Use at least 12 characters. Changing your password signs out other sessions.</small>
        </label>
        <div className="profile-form-actions">
          <button className="button button-primary" disabled={saving || unchanged}>{saving ? "Saving…" : "Save profile"}</button>
          {message && <span className={`settings-notice settings-notice-${message.tone}`} role={message.tone === "error" ? "alert" : "status"}>{message.text}</span>}
        </div>
      </form>
    </section>
  );
}

function AppearanceSettings({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  return (
    <section className="panel settings-section">
      <div className="settings-section-head"><div><h2>Appearance</h2><p>Your theme preference is saved locally to this browser.</p></div></div>
      <SettingRow label="Theme" description="Choose the appearance that works best for you.">
        <button className="theme-switch" type="button" onClick={onToggleTheme} aria-label="Toggle theme">
          <span className={theme === "light" ? "selected" : ""}><Sun size={15} /> Light</span>
          <span className={theme === "dark" ? "selected" : ""}><Moon size={15} /> Dark</span>
        </button>
      </SettingRow>
    </section>
  );
}

function SecuritySettings({ role, actualRole, onRoleChange }: { role: Role; actualRole: Role; onRoleChange: (role: Role) => void }) {
  const previewRoles: Role[] = actualRole === "Admin" ? ["Admin", "Organization", "User"] : ["Organization", "User"];

  return (
    <>
      <section className="panel settings-section">
        <div className="settings-section-head"><div><h2>Security & roles</h2><p>These states are enforced by the API and cannot be changed from presentation-only controls.</p></div></div>
        <SecurityStatus icon={LockKeyhole} label="Tenant isolation" description="Retrieval and conversation history are scoped to the active organization." />
        <SecurityStatus icon={ShieldCheck} label="Citation enforcement" description="Grounded answers require citations that match authorized retrieved chunks." />
        <SecurityStatus icon={KeyRound} label="Session protection" description="Access tokens expire and refresh sessions rotate through HttpOnly cookies." />
      </section>
      {actualRole !== "User" && (
        <section className="panel settings-section">
          <div className="settings-section-head"><div><h2>Role preview</h2><p>Preview presentation states without changing server authorization.</p></div></div>
          <SettingRow label="Current role" description="The API remains authoritative for every action.">
            <select className="settings-select" value={role} onChange={(event) => onRoleChange(event.target.value as Role)}>
              {previewRoles.map((preview) => <option key={preview}>{preview}</option>)}
            </select>
          </SettingRow>
          <div className="role-cards">
            {previewRoles.includes("Admin") && <RoleCard icon={ShieldCheck} title="Admin" description="System monitoring and cross-organization controls" active={role === "Admin"} onClick={() => onRoleChange("Admin")} />}
            <RoleCard icon={Users} title="Organization" description="Manage one organization’s members and sources" active={role === "Organization"} onClick={() => onRoleChange("Organization")} />
            <RoleCard icon={UserRound} title="User" description="Ask questions from authorized workspace sources" active={role === "User"} onClick={() => onRoleChange("User")} />
          </div>
        </section>
      )}
    </>
  );
}

function IntegrationsSettings() {
  const [readiness, setReadiness] = useState<"checking" | "ready" | "unavailable">("checking");

  async function refreshReadiness() {
    setReadiness("checking");
    try {
      await getReadiness();
      setReadiness("ready");
    } catch {
      setReadiness("unavailable");
    }
  }

  useEffect(() => {
    let active = true;
    getReadiness().then(() => { if (active) setReadiness("ready"); }).catch(() => { if (active) setReadiness("unavailable"); });
    return () => { active = false; };
  }, []);

  const statusLabel = readiness === "ready" ? "Ready" : readiness === "checking" ? "Checking" : "Unavailable";
  const statusClass = readiness === "ready" ? "status-active" : readiness === "checking" ? "status-pending" : "status-error";

  return (
    <section className="panel settings-section">
      <div className="settings-section-head"><div><h2>Integrations</h2><p>Review the live API and provider readiness visible to this workspace.</p></div></div>
      <div className="integration-grid">
        <div className="integration-card"><span className="setting-icon"><Activity size={16} /></span><div><strong>API service</strong><p>{import.meta.env.VITE_API_BASE_URL ? "Configured public API endpoint" : "API endpoint is not configured"}</p></div><span className={`status-pill ${statusClass}`}><span />{statusLabel}</span></div>
        <div className="integration-card"><span className="setting-icon"><LockKeyhole size={16} /></span><div><strong>Credentialed session</strong><p>Short-lived access token with rotating refresh session.</p></div><span className="status-pill status-active"><span />Active</span></div>
        <div className="integration-card"><span className="setting-icon"><ShieldCheck size={16} /></span><div><strong>Single sign-on</strong><p>Enable OIDC at deployment time when enterprise identity is required.</p></div><span className="status-pill status-pending"><span />Optional</span></div>
      </div>
      <button className="button button-secondary" type="button" onClick={() => void refreshReadiness()}>Refresh status</button>
    </section>
  );
}

function NotificationsSettings() {
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadNotifications() {
    setLoading(true);
    setError("");
    try {
      setNotifications(await listNotifications(30));
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Could not load notifications.";
      setNotifications([]);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    listNotifications(30).then((items) => { if (active) setNotifications(items); }).catch((requestError) => {
      if (!active) return;
      const message = requestError instanceof Error ? requestError.message : "Could not load notifications.";
      setNotifications([]);
      setError(message);
    });
    return () => { active = false; };
  }, []);

  return (
    <section className="panel settings-section">
      <div className="settings-section-head"><div><h2>Notifications</h2><p>Recent safe activity from your current organization.</p></div><button className="button button-secondary" type="button" onClick={() => void loadNotifications()} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button></div>
      {error && <div className="notice notice-error"><Activity size={16} /><span>{error}</span></div>}
      {notifications.length ? <div className="notification-settings-list">{notifications.map((notification) => <div className="notification-item notification-settings-item" key={notification.id}><span className={`notification-status ${notification.severity}`} /><div><strong>{notification.title}</strong><small>{notification.detail}</small><time>{new Date(notification.created_at).toLocaleString()}</time></div></div>)}</div> : !error && <div className="empty-state"><Activity size={20} /><strong>No recent notifications</strong><span>Security and workspace activity will appear here as it happens.</span></div>}
    </section>
  );
}

export function SettingsPage({ currentName, theme, onToggleTheme, role, actualRole, onRoleChange, onProfileUpdated }: SettingsPageProps) {
  const [section, setSection] = useState<SettingsSection>("general");

  function renderSection() {
    switch (section) {
      case "general":
        return <><ProfileSettings key={currentName} currentName={currentName} onProfileUpdated={onProfileUpdated} /><AppearanceSettings theme={theme} onToggleTheme={onToggleTheme} /></>;
      case "security":
        return <SecuritySettings role={role} actualRole={actualRole} onRoleChange={onRoleChange} />;
      case "integrations":
        return <IntegrationsSettings />;
      case "notifications":
        return <NotificationsSettings />;
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Workspace administration" title="Settings" description="Manage your profile, security context, integrations, and workspace activity." />
      <div className="settings-layout">
        <SettingsNav active={section} onChange={setSection} />
        <div className="settings-content">{renderSection()}</div>
      </div>
    </div>
  );
}
