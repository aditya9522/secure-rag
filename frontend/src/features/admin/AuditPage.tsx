import { lazy, Suspense, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, AlertTriangle, Building2, Check, Download, Gauge, Plus, ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";
import { createOrganization, getAdminMetrics, getReadiness, listAudit, type AdminMetrics, type OrganizationCreationResponse } from "../../lib/api";
import { MetricCard } from "../../components/ui/MetricCard";
import { HealthRow, PolicyEvent } from "../../components/ui/Rows";
import { PageHeader, PanelHeading } from "../../components/ui/PageHeader";

const AuditCharts = lazy(() => import("./AuditCharts").then((module) => ({ default: module.AuditCharts })));

type Readiness = "checking" | "ready" | "unavailable";
type AuditEvent = Record<string, unknown>;

function CreateOrganizationForm({ onCreated }: { onCreated: (organization: OrganizationCreationResponse) => void }) {
  const [organizationName, setOrganizationName] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [creating, setCreating] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    try {
      const organization = await createOrganization({
        name: organizationName.trim(),
        owner_email: ownerEmail.trim(),
        owner_full_name: ownerName.trim(),
        owner_password: ownerPassword,
      });
      onCreated(organization);
      setOrganizationName("");
      setOwnerName("");
      setOwnerEmail("");
      setOwnerPassword("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Organization creation failed.";
      toast.error(message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="panel organization-create-panel">
      <PanelHeading title="Create an organization" action={<span className="text-button">Owner gets organization admin access</span>} />
      <p className="form-help">Create the first owner account with a temporary password. They can sign in immediately, upload governed sources, and invite members.</p>
      <form className="organization-create-form" onSubmit={submit}>
        <label>Organization name<input value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} minLength={2} maxLength={160} required /></label>
        <label>Owner full name<input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} minLength={2} maxLength={160} required /></label>
        <label>Owner email<input type="email" value={ownerEmail} onChange={(event) => setOwnerEmail(event.target.value)} required /></label>
        <label>Temporary password<input type="password" value={ownerPassword} onChange={(event) => setOwnerPassword(event.target.value)} minLength={12} maxLength={128} autoComplete="new-password" required /><small>At least 12 characters; share it through a secure channel.</small></label>
        <div className="form-actions">
          <button type="submit" className="button button-primary" disabled={creating}>{creating ? "Creating…" : "Create organization"}</button>
        </div>
      </form>
    </section>
  );
}

function ServiceHealthPanel({ readiness, hasMetrics }: { readiness: Readiness; hasMetrics: boolean }) {
  const status = readiness === "ready" ? "Healthy" : readiness === "checking" ? "Checking" : "Unavailable";

  return (
    <section className="panel">
      <PanelHeading title="Service health" action={<span className={`live-indicator ${readiness !== "ready" ? "health-muted" : ""}`}><span />{readiness === "ready" ? "Live" : readiness}</span>} />
      <HealthRow label="API gateway" detail="Current readiness probe" value={status} />
      <HealthRow label="Retrieval service" detail="Provider dependency check" value={status} />
      <HealthRow label="Generation service" detail="Provider dependency check" value={status} />
      <HealthRow label="Audit store" detail="PostgreSQL-backed metrics" value={hasMetrics ? "Healthy" : "Unavailable"} />
    </section>
  );
}

function PolicyEventsPanel({ events }: { events: AuditEvent[] }) {
  return (
    <section className="panel policy-events">
      <PanelHeading title="Recent policy events" action={<span className="text-button">{events.length || "No"} events</span>} />
      {events.slice(0, 4).map((event, index) => (
        <PolicyEvent
          key={String(event.id ?? index)}
          type={String(event.event_type ?? "System event")}
          detail={event.metadata ? JSON.stringify(event.metadata) : "Recorded by the API"}
          time={event.created_at ? new Date(String(event.created_at)).toLocaleString() : "Recently"}
          good={String(event.event_type).includes("allowed")}
        />
      ))}
      {!events.length && <div className="empty-state"><Check size={20} /><strong>Monitoring is ready</strong><span>Policy events will appear after authenticated workspace activity.</span></div>}
    </section>
  );
}

function AdminMetricGrid({ metrics }: { metrics: AdminMetrics | null }) {
  return (
    <div className="metric-grid">
      <MetricCard label="Audit events today" value={metrics ? String(metrics.audit_events_today) : "—"} trend="Live" icon={Activity} positive />
      <MetricCard label="Organizations" value={metrics ? String(metrics.organizations) : "—"} trend="Active tenants" icon={Gauge} />
      <MetricCard label="Documents" value={metrics ? String(metrics.documents) : "—"} trend="Indexed sources" icon={ShieldCheck} positive />
      <MetricCard label="Users" value={metrics ? String(metrics.users) : "—"} trend="Registered accounts" icon={AlertTriangle} iconTone="amber" />
    </div>
  );
}

export function AuditPage() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [readiness, setReadiness] = useState<Readiness>("checking");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createdOrganization, setCreatedOrganization] = useState<OrganizationCreationResponse | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [summary, audit] = await Promise.all([getAdminMetrics(), listAudit(20)]);
        if (active) {
          setMetrics(summary);
          setEvents(audit);
          setError("");
        }
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : "Monitoring data is unavailable.");
      }

      try {
        await getReadiness();
        if (active) setReadiness("ready");
      } catch {
        if (active) setReadiness("unavailable");
      }
    }

    void load();
    const interval = window.setInterval(() => void load(), 15_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  function exportReport() {
    const content = JSON.stringify({ generated_at: new Date().toISOString(), metrics, readiness, events }, null, 2);
    const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `aegisrag-audit-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setNotice("Audit report downloaded.");
    toast.success("Audit report downloaded.");
  }

  function handleOrganizationCreated(created: OrganizationCreationResponse) {
    setCreatedOrganization(created);
    setNotice(`${created.organization.name} is ready for ${created.owner.email}.`);
    setCreateOpen(false);
    toast.success(`${created.organization.name} created successfully.`);
    void getAdminMetrics().then(setMetrics).catch(() => undefined);
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Admin console"
        title="Audit & monitoring"
        description="A live view of system health, access decisions, and retrieval activity."
        action={<div className="page-actions"><button className="button button-primary" onClick={() => { setCreateOpen((open) => !open); setCreatedOrganization(null); }}><Plus size={16} /> Create organization</button><button className="button button-secondary" onClick={exportReport}><Download size={16} /> Export report</button></div>}
      />
      {notice && <div className="notice notice-success"><Check size={16} /><span>{notice}</span></div>}
      {error && <div className="notice notice-error"><AlertTriangle size={16} /><span>{error}</span></div>}
      {createOpen && <CreateOrganizationForm onCreated={handleOrganizationCreated} />}
      {createdOrganization && <section className="notice notice-success"><Building2 size={16} /><span><strong>{createdOrganization.organization.name}</strong> created with owner access for {createdOrganization.owner.email}.</span></section>}
      <AdminMetricGrid metrics={metrics} />
      <Suspense fallback={<div className="audit-chart-loading" role="status">Loading audit visualizations…</div>}><AuditCharts events={events} metrics={metrics} /></Suspense>
      <div className="monitoring-grid"><ServiceHealthPanel readiness={readiness} hasMetrics={Boolean(metrics)} /><PolicyEventsPanel events={events} /></div>
    </div>
  );
}
