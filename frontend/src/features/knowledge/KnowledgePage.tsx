import { useEffect, useRef, useState } from "react";
import { Activity, Check, Database, FileText, MoreHorizontal, Search, ShieldCheck, SlidersHorizontal, Upload, Users, X } from "lucide-react";
import { listDocuments, revokeDocument, uploadDocument, type Classification, type DocumentSummary } from "../../lib/api";
import { PageHeader } from "../../components/ui/PageHeader";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import toast from "react-hot-toast";

const classifications: Classification[] = ["public", "internal", "confidential", "restricted"];
type SourceStatus = "all" | "active" | "indexing" | "failed";

function SourceTableRow({ document, canManage, onRevoke }: { document: DocumentSummary; canManage: boolean; onRevoke: () => void }) {
  const statusClass = document.status === "active" ? "status-active" : document.status === "failed" ? "status-error" : "status-pending";
  return <div className="table-row"><div className="member-cell"><span className="file-icon"><FileText size={15} /></span><span><strong>{document.title}</strong><small>{document.classification} · {document.chunks_indexed} chunks</small></span></div><span className="scope-text"><Users size={13} /> {document.allowed_groups.join(", ") || "Organization"}</span><span className="table-muted">{new Date(document.updated_at).toLocaleDateString()}</span><span className={`status-pill ${statusClass}`}><span />{document.status}</span>{canManage ? <button className="icon-button subtle" onClick={onRevoke} aria-label={`Revoke ${document.title}`}><MoreHorizontal size={17} /></button> : <span />}</div>;
}

export function KnowledgePage({ canManage }: { canManage: boolean }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<SourceStatus>("all");
  const [classificationFilter, setClassificationFilter] = useState<Classification | "all">("all");
  const [groupFilter, setGroupFilter] = useState("");
  const [classification, setClassification] = useState<Classification>("internal");
  const [groups, setGroups] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [confirmDocument, setConfirmDocument] = useState<DocumentSummary | null>(null);
  const [revoking, setRevoking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const filterRef = useRef<HTMLDivElement>(null);
  const loadDocuments = () => listDocuments().then(setDocuments).catch((requestError) => { setDocuments([]); setError(requestError instanceof Error ? requestError.message : "Could not load knowledge sources."); });
  useEffect(() => { void loadDocuments(); }, []);
  useEffect(() => {
    if (!filterOpen) return;
    const dismiss = (event: PointerEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) setFilterOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [filterOpen]);

  async function onFileSelected(file?: File) {
    if (!file) return;
    setLoading(true); setNotice(""); setError("");
    try { await uploadDocument(file, { classification, allowed_groups: groups.split(",").map((group) => group.trim()).filter(Boolean), source_uri: sourceUri || undefined }); const message = `${file.name} is indexed and available only within the configured access scope.`; setNotice(message); toast.success(message); setUploadOpen(false); setGroups(""); setSourceUri(""); await loadDocuments(); }
    catch (requestError) { const message = requestError instanceof Error ? requestError.message : "Upload failed."; setError(message); toast.error(message); }
    finally { setLoading(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function revoke() {
    if (!confirmDocument) return;
    setRevoking(true); setError("");
    try { await revokeDocument(confirmDocument.id); const message = `${confirmDocument.title} was revoked.`; setNotice(message); toast.success(message); setConfirmDocument(null); await loadDocuments(); }
    catch (requestError) { const message = requestError instanceof Error ? requestError.message : "Could not revoke source."; setError(message); toast.error(message); }
    finally { setRevoking(false); }
  }

  const groupsInUse = [...new Set(documents.flatMap((document) => document.allowed_groups))].sort((left, right) => left.localeCompare(right));
  const hasFilters = Boolean(search.trim() || statusFilter !== "all" || classificationFilter !== "all" || groupFilter);
  const visibleDocuments = documents.filter((document) => {
    const matchesSearch = `${document.title} ${document.classification} ${document.allowed_groups.join(" ")}`.toLowerCase().includes(search.trim().toLowerCase());
    const matchesStatus = statusFilter === "all" || document.status === statusFilter;
    const matchesClassification = classificationFilter === "all" || document.classification === classificationFilter;
    const matchesGroup = !groupFilter || document.allowed_groups.includes(groupFilter);
    return matchesSearch && matchesStatus && matchesClassification && matchesGroup;
  });
  const clearFilters = () => { setSearch(""); setStatusFilter("all"); setClassificationFilter("all"); setGroupFilter(""); };
  const failedCount = documents.filter((document) => document.status === "failed").length;
  const indexingCount = documents.filter((document) => document.status === "indexing").length;
  const indexStatus = loading || indexingCount ? "Indexing" : failedCount ? `${failedCount} failed` : "Healthy";
  return <div className="page-stack"><PageHeader eyebrow="Knowledge base" title="Connected knowledge" description={canManage ? "Manage the sources your organization has approved for secure retrieval." : "Browse the sources you are authorized to access."} action={canManage ? <button className="button button-primary" onClick={() => setUploadOpen(!uploadOpen)}><Upload size={16} /> Add source</button> : undefined} />
    {notice && <div className="notice notice-success"><Check size={17} /><span>{notice}</span><button onClick={() => setNotice("")} aria-label="Dismiss"><X size={15} /></button></div>}{error && <div className="notice notice-error"><X size={17} /><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss"><X size={15} /></button></div>}
    {uploadOpen && <section className="panel inline-form"><form onSubmit={(event) => { event.preventDefault(); inputRef.current?.click(); }}><h3>Add a governed source</h3><label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as Classification)}>{classifications.map((value) => <option key={value}>{value}</option>)}</select></label><label>Access groups<input value={groups} onChange={(event) => setGroups(event.target.value)} placeholder="engineering, support" /><small>Comma-separated groups. Leave empty to make the source available to all active members.</small></label><label className="field-wide">Source URI <span className="optional-label">optional</span><input type="url" value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} placeholder="https://…" /></label><input ref={inputRef} type="file" hidden accept=".txt,.md,.pdf,.docx,.csv,.json" onChange={(event) => void onFileSelected(event.target.files?.[0])} /><div><button className="button button-primary" disabled={loading}>{loading ? "Uploading…" : "Choose file"}</button><button type="button" className="button button-secondary" onClick={() => setUploadOpen(false)}>Cancel</button></div></form></section>}
    <div className="source-summary"><div className="summary-card"><Database size={19} /><div><strong>{documents.length || "—"}</strong><span>Visible sources</span></div></div><div className="summary-card"><ShieldCheck size={19} /><div><strong>Protected</strong><span>Access boundary</span></div></div><div className="summary-card"><Activity size={19} /><div><strong>{indexStatus}</strong><span>Index status</span></div></div></div><section className="panel"><div className="table-toolbar"><div className="search-field"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search sources" aria-label="Search sources" /></div><div className="source-filter-wrap" ref={filterRef}><button className="filter-button" type="button" onClick={() => setFilterOpen((open) => !open)} aria-expanded={filterOpen} aria-haspopup="dialog"><SlidersHorizontal size={15} /> {hasFilters ? `Filters (${[statusFilter !== "all", classificationFilter !== "all", Boolean(groupFilter)].filter(Boolean).length + (search.trim() ? 1 : 0)})` : "Filter"}</button>{filterOpen && <div className="source-filter-panel" role="dialog" aria-label="Filter sources"><label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as SourceStatus)}><option value="all">All statuses</option><option value="active">Active</option><option value="indexing">Indexing</option><option value="failed">Failed</option></select></label><label>Classification<select value={classificationFilter} onChange={(event) => setClassificationFilter(event.target.value as Classification | "all")}><option value="all">All classifications</option>{classifications.map((value) => <option key={value}>{value}</option>)}</select></label><label>Access group<select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option value="">All groups</option>{groupsInUse.map((group) => <option key={group}>{group}</option>)}</select></label><button className="text-button" type="button" onClick={clearFilters}>Clear filters</button></div>}</div></div><div className="source-table"><div className="table-row table-head"><span>Source</span><span>Access scope</span><span>Last indexed</span><span>Status</span><span /></div>{visibleDocuments.length ? visibleDocuments.map((document) => <SourceTableRow key={document.id} document={document} canManage={canManage} onRevoke={() => setConfirmDocument(document)} />) : <div className="empty-state"><Database size={20} /><strong>{hasFilters ? "No matching sources" : "No sources connected yet"}</strong><span>{hasFilters ? "Adjust or clear your search and filters." : "Add an approved document to start building this organization’s knowledge base."}</span></div>}</div></section>{confirmDocument && <ConfirmDialog title={`Revoke ${confirmDocument.title}?`} description="This source will be removed from future retrieval for the organization. Existing audit records are retained." confirmLabel="Revoke source" busy={revoking} onConfirm={() => void revoke()} onCancel={() => { if (!revoking) setConfirmDocument(null); }} />}
  </div>;
}
