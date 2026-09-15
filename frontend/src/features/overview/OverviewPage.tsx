import { lazy, Suspense, useEffect, useState } from "react";
import { Activity, ArrowUpRight, Database, MessageSquare, Upload, Users } from "lucide-react";
import { listConversations, listDocuments, listMembers, type ConversationSummary, type DocumentSummary, type MemberSummary } from "../../lib/api";
import type { View } from "../../types";
import { formatRelativeDate } from "../../lib/date";
import { MetricCard } from "../../components/ui/MetricCard";
import { ActivityRow, QuickAction } from "../../components/ui/Rows";
import { PageHeader, PanelHeading } from "../../components/ui/PageHeader";
import type { Role } from "../../types";

const WorkspaceTrendChart = lazy(() => import("./WorkspaceTrendChart").then((module) => ({ default: module.WorkspaceTrendChart })));

export function OverviewPage({ identity, canManageMembers, actualRole, onNavigate }: { identity: string; canManageMembers: boolean; actualRole: Role; onNavigate: (view: View) => void }) {
  const [sourceCount, setSourceCount] = useState<number | null>(null);
  const [memberCount, setMemberCount] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [error, setError] = useState("");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let active = true;
    void Promise.all([listDocuments(), listConversations(), canManageMembers ? listMembers() : Promise.resolve([])])
      .then(([sourceItems, savedConversations, memberItems]) => { if (active) { setDocuments(sourceItems); setConversations(savedConversations); setMembers(canManageMembers ? memberItems : []); setSourceCount(sourceItems.length); setMemberCount(canManageMembers ? memberItems.length : null); } })
      .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : "Workspace summary is unavailable."); });
    return () => { active = false; };
  }, [canManageMembers]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 60_000); return () => window.clearInterval(timer); }, []);

  return <div className="page-stack"><PageHeader eyebrow="Command center" title={`Good morning, ${identity.split(" ")[0]}`} description="A live summary of this organization’s authorized workspace activity." action={<button className="button button-primary" onClick={() => onNavigate("chat")}><MessageSquare size={16} /> Ask a question</button>} />
    {error && <div className="notice notice-error"><Activity size={16} /><span>{error}</span></div>}
    <div className="metric-grid"><MetricCard label="Saved conversations" value={String(conversations.length)} trend="Your workspace history" icon={MessageSquare} /><MetricCard label="Visible knowledge sources" value={sourceCount === null ? "—" : String(sourceCount)} trend="Authorized sources" icon={Database} /><MetricCard label="Organization members" value={memberCount === null ? "—" : String(memberCount)} trend={canManageMembers ? "Current organization" : "Admin-only metric"} icon={Users} /><MetricCard label="Access boundary" value="Active" trend="Tenant policy enforced" icon={Activity} positive /></div>
    <div className="overview-grid"><section className="panel activity-panel"><PanelHeading title="Workspace activity" action={<span className="text-button">Live data</span>} />{conversations.length ? <div className="activity-list">{conversations.slice(0, 4).map((conversation) => <ActivityRow key={conversation.id} icon={MessageSquare} color="purple" title={conversation.title || "Untitled conversation"} detail="Saved in the current organization" time={formatRelativeDate(conversation.updated_at, now)} />)}</div> : <div className="empty-state"><MessageSquare size={20} /><strong>No conversations yet</strong><span>Ask an authorized workspace question to start your first conversation.</span></div>}</section><section className="panel quick-panel"><PanelHeading title="Quick actions" /><QuickAction icon={MessageSquare} title="Ask workspace" description="Query authorized organization knowledge" onClick={() => onNavigate("chat")} />{canManageMembers && <QuickAction icon={Upload} title="Add knowledge" description="Upload a governed source" onClick={() => onNavigate("knowledge")} />}{canManageMembers && <QuickAction icon={Users} title="Invite members" description="Manage roles and access" onClick={() => onNavigate("members")} />}<QuickAction icon={Database} title="Review sources" description="See your authorized knowledge base" onClick={() => onNavigate("knowledge")} /></section></div>
    <Suspense fallback={<section className="panel workspace-trend trend-loading" aria-label="Loading activity chart">Loading activity chart…</section>}><WorkspaceTrendChart conversations={conversations} documents={documents} members={members} canManageMembers={canManageMembers} /></Suspense>
    <section className="panel role-guide"><PanelHeading title={actualRole === "User" ? "Your member workflow" : "Workspace workflow"} action={<span className="text-button">Role-aware</span>} /><div className="guide-steps"><div><strong>1. Ask</strong><span>Use Secure chat for questions about authorized sources.</span></div><div><strong>2. Verify</strong><span>Review answer mode and citations in Answer context.</span></div><div><strong>3. Govern</strong><span>{canManageMembers ? "Upload sources and manage member access." : "Your organization administrator controls sources and access."}</span></div></div></section>
    <section className="panel"><PanelHeading title="Security posture" action={<button className="text-button" onClick={() => onNavigate("settings")}>Review settings <ArrowUpRight size={14} /></button>} /><div className="activity-list"><ActivityRow icon={Activity} color="green" title="Tenant isolation enabled" detail="The active organization scopes retrieval and history." time="Current" /><ActivityRow icon={Database} color="blue" title="Source visibility protected" detail="PostgreSQL metadata and retrieval ACLs are applied together." time="Current" /><ActivityRow icon={Users} color="purple" title="Role-aware workspace" detail={canManageMembers ? "Organization access controls are available to you." : "Member administration is restricted to organization administrators."} time="Current" /></div></section>
  </div>;
}
