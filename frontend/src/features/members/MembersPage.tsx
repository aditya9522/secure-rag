import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ArrowUpRight, Check, Copy, MoreHorizontal, Plus, Search, Users, X } from "lucide-react";
import { inviteMember, listMembers, type Classification, type MemberRole, type MemberSummary, updateMember } from "../../lib/api";
import { PageHeader } from "../../components/ui/PageHeader";
import toast from "react-hot-toast";

const classifications: Classification[] = ["public", "internal", "confidential", "restricted"];

function groupsFromInput(value: string) {
  return [...new Set(value.split(",").map((group) => group.trim()).filter(Boolean))];
}

export function MembersPage() {
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [editing, setEditing] = useState<MemberSummary | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [editRole, setEditRole] = useState<MemberRole>("member");
  const [groups, setGroups] = useState("");
  const [classification, setClassification] = useState<Classification>("internal");
  const [notice, setNotice] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");

  const loadMembers = () => listMembers().then(setMembers).catch((requestError) => { setMembers([]); setError(requestError instanceof Error ? requestError.message : "Could not load organization members."); });
  useEffect(() => { void loadMembers(); }, []);

  function resetForm() {
    setEmail(""); setName(""); setRole("member"); setEditRole("member"); setGroups(""); setClassification("internal");
  }

  async function submitInvite(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await inviteMember({ email, full_name: name, role, groups: groupsFromInput(groups), classification_max: classification });
      const link = `${window.location.origin}/?invite=${encodeURIComponent(result.invitation_token)}`;
      const message = `Invitation created. It expires ${new Date(result.expires_at).toLocaleString()}.`;
      setInviteLink(link); setNotice(message); toast.success(message);
      if (navigator.clipboard) await navigator.clipboard.writeText(link).catch(() => undefined);
      setInviteOpen(false); resetForm();
    } catch (requestError) { const message = requestError instanceof Error ? requestError.message : "Invitation failed."; setError(message); toast.error(message); }
    finally { setBusy(false); }
  }

  function openEditor(member: MemberSummary) {
    if (member.role === "owner") return;
    setEditing(member); setEditRole(member.status === "suspended" ? "suspended" : member.role === "admin" ? "admin" : "member"); setGroups(member.groups.join(", ")); setClassification((classifications.includes(member.classification_max as Classification) ? member.classification_max : "internal") as Classification); setError("");
  }

  async function saveMember(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    setBusy(true); setError(""); setNotice("");
    try { await updateMember(editing.user_id, { role: editRole, groups: groupsFromInput(groups), classification_max: classification }); const message = `${editing.full_name}'s access was updated.`; setNotice(message); toast.success(message); setEditing(null); await loadMembers(); }
    catch (requestError) { const message = requestError instanceof Error ? requestError.message : "Could not update member access."; setError(message); toast.error(message); }
    finally { setBusy(false); }
  }

  const visibleMembers = members.filter((member) => `${member.full_name} ${member.email} ${member.role}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="page-stack">
    <PageHeader eyebrow="Access control" title="Members & access" description="Manage organization membership, roles, and group-scoped access." action={<button className="button button-primary" onClick={() => { setInviteOpen(true); setEditing(null); setError(""); }}><Plus size={16} /> Invite member</button>} />
    {notice && <div className="notice notice-success"><Check size={16} /><span>{notice}</span><button onClick={() => { setNotice(""); setInviteLink(""); }} aria-label="Dismiss notice"><X size={15} /></button></div>}
    {error && <div className="notice notice-error"><X size={16} /><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button></div>}
    {inviteOpen && <section className="panel inline-form"><form onSubmit={submitInvite}><h3>Invite a member</h3><label>Full name<input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} /></label><label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Role<select value={role} onChange={(event) => setRole(event.target.value as "admin" | "member")}><option value="member">Member</option><option value="admin">Administrator</option></select></label><label>Classification clearance<select value={classification} onChange={(event) => setClassification(event.target.value as Classification)}>{classifications.map((value) => <option key={value}>{value}</option>)}</select></label><label className="field-wide">Groups<input value={groups} onChange={(event) => setGroups(event.target.value)} placeholder="engineering, support" /><small>Comma-separated groups. Keep access least-privileged.</small></label><div><button className="button button-primary" disabled={busy}>{busy ? "Creating…" : "Create invitation"}</button><button type="button" className="button button-secondary" onClick={() => { setInviteOpen(false); resetForm(); }}>Cancel</button></div></form></section>}
    {editing && <section className="panel inline-form"><form onSubmit={saveMember}><h3>Update access for {editing.full_name}</h3><label>Role<select value={editRole} onChange={(event) => setEditRole(event.target.value as MemberRole)}><option value="member">Member</option><option value="admin">Administrator</option><option value="suspended">Suspended</option></select></label><label>Classification clearance<select value={classification} onChange={(event) => setClassification(event.target.value as Classification)}>{classifications.map((value) => <option key={value}>{value}</option>)}</select></label><label className="field-wide">Groups<input value={groups} onChange={(event) => setGroups(event.target.value)} placeholder="engineering, support" /></label><div><button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Save access"}</button><button type="button" className="button button-secondary" onClick={() => setEditing(null)}>Cancel</button></div></form></section>}
    <div className="role-banner"><div className="role-banner-icon"><Users size={18} /></div><div><strong>Role-based access control</strong><p>Every question and source is evaluated against the member’s current organization, groups, and classification clearance.</p></div><button className="text-button" onClick={() => setNotice("Access is enforced by the API and retrieval policy on every request.")}>View policy <ArrowUpRight size={14} /></button></div>
    <section className="panel"><div className="table-toolbar"><h3 className="table-title">Organization members <span>{members.length || "—"}</span></h3><div className="search-field compact"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search members" aria-label="Search members" /></div></div><div className="member-table"><div className="table-row table-head"><span>Member</span><span>Role</span><span>Groups</span><span>Status</span><span /></div>{visibleMembers.length ? visibleMembers.map((member) => <div className="table-row" key={member.user_id}><div className="member-cell"><span className="profile-avatar table-avatar">{member.full_name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</span><span><strong>{member.full_name}</strong><small>{member.email}</small></span></div><span className="role-text">{member.role}</span><span className="org-count">{member.groups.join(", ") || "No groups"}</span><span className={`status-pill ${member.status === "active" ? "status-active" : "status-pending"}`}><span />{member.status}</span><button className="icon-button subtle" disabled={member.role === "owner"} onClick={() => openEditor(member)} aria-label={`Manage ${member.full_name}`} title={member.role === "owner" ? "Owner access cannot be changed" : "Manage access"}><MoreHorizontal size={17} /></button></div>) : <div className="empty-state"><Users size={20} /><strong>{search ? "No matching members" : "No member data available"}</strong><span>{search ? "Try a different name, email, or role." : "Member data will appear here when the organization is ready."}</span></div>}</div></section>
    {inviteLink && <section className="panel invite-share"><div><strong>Invitation link ready</strong><span>Treat this one-time link like a secret and share it with the invited person.</span><input className="invite-link-input" value={inviteLink} readOnly aria-label="Invitation link" /></div><button className="button button-secondary" onClick={() => void navigator.clipboard?.writeText(inviteLink)}><Copy size={15} /> Copy link</button></section>}
  </div>;
}
