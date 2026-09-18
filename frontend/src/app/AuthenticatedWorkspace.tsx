import { useEffect, useMemo, useRef, useState } from "react";
import type { AuthResponse, OrganizationSummary } from "../lib/api";
import { logout, setAccessToken, switchOrganization } from "../lib/api";
import { navItems } from "../data/navigation";
import type { OrganizationOption, Role, Theme, View } from "../types";
import { Header } from "../components/layout/Header";
import { Sidebar } from "../components/layout/Sidebar";
import { HelpPanel } from "../components/layout/HelpPanel";
import { AuditPage } from "../features/admin/AuditPage";
import { ChatPage } from "../features/chat/ChatPage";
import { KnowledgePage } from "../features/knowledge/KnowledgePage";
import { MembersPage } from "../features/members/MembersPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { FeedbackPage } from "../features/feedback/FeedbackPage";

function organizationOption(organization: OrganizationSummary): OrganizationOption {
  return {
    id: organization.id,
    name: organization.name,
    detail: `${organization.role} access`,
    initials: organization.name.slice(0, 1).toUpperCase(),
    color: organization.role === "owner" ? "violet" : "blue",
  };
}

function sessionRole(session: AuthResponse): Role {
  if (session.user.is_system_admin) return "Admin";
  return ["owner", "admin"].includes(session.current_organization.role) ? "Organization" : "User";
}

function renderPage(view: View, identity: string, organization: OrganizationOption, canManageMembers: boolean, canGrantAdministrator: boolean, previewRole: Role, actualRole: Role, theme: Theme, onNavigate: (view: View) => void, onToggleTheme: () => void, onRoleChange: (role: Role) => void, onProfileUpdated: (profile: { user: AuthResponse["user"]; current_organization: OrganizationSummary; organizations: OrganizationSummary[] }) => void) {
  if (view === "overview") return <OverviewPage key={organization.id} identity={identity} canManageMembers={canManageMembers} actualRole={actualRole} onNavigate={onNavigate} />;
  if (view === "chat") return <ChatPage key={organization.id} organization={organization.name} identity={identity} onNavigate={onNavigate} />;
  if (view === "knowledge") return <KnowledgePage key={organization.id} canManage={canManageMembers} />;
  if (view === "members") return <MembersPage key={organization.id} canGrantAdministrator={canGrantAdministrator} />;
  if (view === "audit") return <AuditPage key={organization.id} />;
  if (view === "feedback") return <FeedbackPage key={organization.id} isPlatformAdmin={actualRole === "Admin"} />;
  return <SettingsPage key={identity} currentName={identity} theme={theme} onToggleTheme={onToggleTheme} role={previewRole} actualRole={actualRole} onRoleChange={onRoleChange} onProfileUpdated={onProfileUpdated} />;
}

export function AuthenticatedWorkspace({ session, onSessionUpdated, onSignedOut }: { session: AuthResponse; onSessionUpdated: (session: AuthResponse) => void; onSignedOut: () => void }) {
  const [view, setView] = useState<View>("chat");
  const [previewRole, setPreviewRole] = useState<Role>(() => sessionRole(session));
  const [theme, setTheme] = useState<Theme>(() => localStorage.getItem("secure-rag.theme") === "dark" ? "dark" : "light");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [workspaceNotice, setWorkspaceNotice] = useState("");
  const [switchingOrganization, setSwitchingOrganization] = useState(false);
  const organizationSwitchRequest = useRef(0);
  const actualRole = sessionRole(session);
  const canManageMembers = ["owner", "admin"].includes(session.current_organization.role);
  const canGrantAdministrator = session.current_organization.role === "owner";
  const organization = organizationOption(session.current_organization);
  const organizations = useMemo(() => session.organizations.map(organizationOption), [session.organizations]);
  const visibleNav = navItems.filter((item) => item.id !== "members" || canManageMembers).filter((item) => item.id !== "audit" || actualRole === "Admin");
  const effectiveView: View = (view === "members" && !canManageMembers) || (view === "audit" && actualRole !== "Admin") ? "chat" : view;
  const navigate = (nextView: View) => { setView(nextView); setSidebarOpen(false); };

  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); localStorage.setItem("secure-rag.theme", theme); }, [theme]);

  async function changeOrganization(next: OrganizationOption) {
    if (!next.id) return;
    const requestId = ++organizationSwitchRequest.current;
    setWorkspaceNotice("");
    setSwitchingOrganization(true);
    try {
      const updated = await switchOrganization(next.id);
      if (requestId === organizationSwitchRequest.current) {
        setPreviewRole(sessionRole(updated));
        onSessionUpdated(updated);
      }
    }
    catch (error) { setWorkspaceNotice(error instanceof Error ? error.message : "Could not switch organization."); }
    finally { if (requestId === organizationSwitchRequest.current) setSwitchingOrganization(false); }
  }

  async function signOut() {
    try { await logout(); }
    finally { setAccessToken(null); onSignedOut(); }
  }

  const updateProfile = (profile: { user: AuthResponse["user"]; current_organization: OrganizationSummary; organizations: OrganizationSummary[] }) => onSessionUpdated({ ...session, ...profile });
  const toggleTheme = () => setTheme((current) => current === "light" ? "dark" : "light");

  return <div className={`app-shell ${effectiveView === "chat" ? "app-shell-chat" : ""}`}><Sidebar view={effectiveView} items={visibleNav} organization={organization} identity={{ name: session.user.full_name, email: session.user.email }} role={actualRole} onNavigate={navigate} open={sidebarOpen} onClose={() => setSidebarOpen(false)} onHelp={() => setHelpOpen(true)} onSignOut={() => void signOut()} /><div className="app-content"><Header organization={organization} organizations={organizations} identity={{ name: session.user.full_name, email: session.user.email }} signedIn role={previewRole} actualRole={actualRole} organizationSwitching={switchingOrganization} onOrganizationChange={(next) => void changeOrganization(next)} theme={theme} onToggleTheme={toggleTheme} onRoleChange={setPreviewRole} onOpenMenu={() => setSidebarOpen(true)} onSignOut={() => void signOut()} /><main className="page-content">{workspaceNotice && <div className="notice notice-error workspace-notice" role="alert">{workspaceNotice}<button onClick={() => setWorkspaceNotice("")} aria-label="Dismiss organization error">×</button></div>}{renderPage(effectiveView, session.user.full_name, organization, canManageMembers, canGrantAdministrator, previewRole, actualRole, theme, navigate, toggleTheme, setPreviewRole, updateProfile)}</main></div>{helpOpen && <HelpPanel onClose={() => setHelpOpen(false)} />}</div>;
}
