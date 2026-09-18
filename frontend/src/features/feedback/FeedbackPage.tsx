import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { AlertTriangle, BarChart3, Check, CheckCircle2, Clock3, Inbox, MessageSquarePlus, Send, ShieldCheck, Star, Tag, UserRound } from "lucide-react";
import toast from "react-hot-toast";
import {
  listAdminFeedback,
  listMyFeedback,
  submitFeedback,
  updateAdminFeedback,
  type FeedbackCategory,
  type FeedbackItem,
  type FeedbackPriority,
  type FeedbackStatus,
} from "../../lib/api";
import { PageHeader, PanelHeading } from "../../components/ui/PageHeader";

const categories: Array<{ value: FeedbackCategory; label: string; description: string }> = [
  { value: "bug", label: "Report a bug", description: "Something is broken or behaving unexpectedly." },
  { value: "feature_request", label: "Request an improvement", description: "Suggest a useful capability or workflow improvement." },
  { value: "answer_quality", label: "Answer quality", description: "Tell us about an answer, source, or citation." },
  { value: "access", label: "Access & permissions", description: "Report an access, invitation, or organization issue." },
  { value: "general", label: "General feedback", description: "Share an observation about your experience." },
];

const statuses: Array<{ value: FeedbackStatus; label: string }> = [
  { value: "new", label: "New" },
  { value: "in_review", label: "In review" },
  { value: "resolved", label: "Resolved" },
  { value: "dismissed", label: "Dismissed" },
];

const priorities: Array<{ value: FeedbackPriority; label: string }> = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
];

function categoryLabel(category: FeedbackCategory) {
  return categories.find((item) => item.value === category)?.label ?? "Feedback";
}

function statusLabel(status: FeedbackStatus) {
  return statuses.find((item) => item.value === status)?.label ?? status;
}

function dateLabel(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function StatusPill({ status }: { status: FeedbackStatus }) {
  return <span className={`feedback-status feedback-status-${status}`}><span />{statusLabel(status)}</span>;
}

function FeedbackInsights({ items, loading, isPlatformAdmin }: { items: FeedbackItem[]; loading: boolean; isPlatformAdmin: boolean }) {
  const openCount = items.filter((item) => item.status === "new" || item.status === "in_review").length;
  const resolvedCount = items.filter((item) => item.status === "resolved").length;
  const ratedItems = items.filter((item) => item.rating !== null);
  const averageRating = ratedItems.length ? (ratedItems.reduce((total, item) => total + (item.rating ?? 0), 0) / ratedItems.length).toFixed(1) : "—";
  const categoryCounts = categories.map((category) => ({ ...category, count: items.filter((item) => item.category === category.value).length }));
  const maxCategoryCount = Math.max(1, ...categoryCounts.map((category) => category.count));

  return <section className="panel feedback-insights-panel" aria-label="Feedback insights">
    <div className="feedback-insights-heading"><div><div className="eyebrow accent-eyebrow">{isPlatformAdmin ? "Platform pulse" : "Your feedback pulse"}</div><h2>{isPlatformAdmin ? "Signals at a glance" : "Make your voice count"}</h2><p>{isPlatformAdmin ? "A quick read of the feedback currently loaded in the operations queue." : "A private summary of the feedback you have shared with the platform team."}</p></div><span className="feedback-insights-icon"><BarChart3 size={17} /></span></div>
    <div className="feedback-stat-grid"><div><span>Total</span><strong>{loading ? "—" : items.length}</strong><small>{isPlatformAdmin ? "Loaded records" : "Your submissions"}</small></div><div><span>Open</span><strong>{loading ? "—" : openCount}</strong><small>Awaiting review</small></div><div><span>Resolved</span><strong>{loading ? "—" : `${resolvedCount}`}</strong><small>{items.length ? `${Math.round((resolvedCount / items.length) * 100)}% of total` : "No activity yet"}</small></div><div><span>Rating</span><strong>{loading ? "—" : averageRating}</strong><small>{ratedItems.length ? `${ratedItems.length} rated` : "Optional rating"}</small></div></div>
    <div className="feedback-signal-chart"><div className="feedback-chart-title"><strong>Signal mix</strong><span>By feedback type</span></div>{loading ? <div className="feedback-chart-skeleton" aria-label="Loading feedback insights"><i /><i /><i /><i /></div> : categoryCounts.map((category) => <div className="feedback-bar-row" key={category.value}><div><span>{category.label}</span><strong>{category.count}</strong></div><div className="feedback-bar-track"><i style={{ width: `${(category.count / maxCategoryCount) * 100}%` }} /></div></div>)}</div>
    <div className="feedback-insights-footer"><span><Clock3 size={14} /> {openCount ? `${openCount} open signal${openCount === 1 ? "" : "s"} to review` : "No open signals"}</span><span><CheckCircle2 size={14} /> {resolvedCount ? `${resolvedCount} resolved` : "Resolution history starts here"}</span></div>
  </section>;
}

function FeedbackComposer({ onSubmitted }: { onSubmitted: (feedback: FeedbackItem) => void }) {
  const [category, setCategory] = useState<FeedbackCategory>("general");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const selectedCategory = categories.find((item) => item.value === category) ?? categories[4];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const feedback = await submitFeedback({
        category,
        subject: subject.trim(),
        message: message.trim(),
        rating: rating ?? undefined,
        source_page: "feedback",
      });
      onSubmitted(feedback);
      setSubject("");
      setMessage("");
      setRating(null);
      toast.success("Feedback submitted. Thank you for helping improve the workspace.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Feedback could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel feedback-composer-panel">
    <PanelHeading title="Share feedback" action={<span className="feedback-private-note"><ShieldCheck size={14} /> Visible to platform administrators</span>} />
    <p className="form-help">Tell us what happened, what you expected, and how we can make the workspace better. Do not include passwords, tokens, or confidential source content.</p>
    <form className="feedback-form" onSubmit={submit}>
      <label>Feedback type<select value={category} onChange={(event) => setCategory(event.target.value as FeedbackCategory)}>{categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select><small>{selectedCategory.description}</small></label>
      <label>Subject<input value={subject} onChange={(event) => setSubject(event.target.value)} minLength={4} maxLength={120} placeholder="A short summary" required /></label>
      <label className="feedback-field-wide">What happened?<textarea value={message} onChange={(event) => setMessage(event.target.value)} minLength={10} maxLength={4000} rows={6} placeholder="Describe the experience, expected result, and any useful steps to reproduce." required /><small>{message.length}/4000 characters</small></label>
      <div className="feedback-rating feedback-field-wide"><span>How would you rate this experience? <em>Optional</em></span><div role="radiogroup" aria-label="Optional feedback rating">{[1, 2, 3, 4, 5].map((value) => <button type="button" key={value} className={rating !== null && value <= rating ? "feedback-star-selected" : ""} onClick={() => setRating(rating === value ? null : value)} aria-label={`${value} out of 5`} aria-pressed={rating === value}><Star size={18} fill="currentColor" /></button>)}</div></div>
      <div className="feedback-form-actions feedback-field-wide"><button type="submit" className="button button-primary" disabled={busy}><Send size={15} />{busy ? "Submitting…" : "Submit feedback"}</button><span>Your message is attached to your current organization and account.</span></div>
    </form>
  </section>;
}

function FeedbackHistory({ items, loading, onRetry }: { items: FeedbackItem[]; loading: boolean; onRetry: () => void }) {
  return <section className="panel feedback-history-panel"><PanelHeading title="Your submissions" action={<span className="text-button">Private to you</span>} />{loading ? <div className="feedback-history-loading" role="status"><Clock3 size={17} />Loading your feedback history…</div> : items.length ? <div className="feedback-history-list">{items.map((item) => <article className="feedback-history-item" key={item.id}><div className="feedback-item-icon"><MessageSquarePlus size={16} /></div><div className="feedback-item-copy"><div className="feedback-item-topline"><strong>{item.subject}</strong><StatusPill status={item.status} /></div><p>{item.message}</p><div className="feedback-item-meta"><span>{categoryLabel(item.category)}</span><span>{dateLabel(item.created_at)}</span></div></div></article>)}</div> : <div className="empty-state"><Inbox size={21} /><strong>No feedback submitted yet</strong><span>Your feedback history will appear here after your first submission.</span><button className="text-button" type="button" onClick={onRetry}>Refresh history</button></div>}</section>;
}

function AdminFeedbackQueue({ items, onUpdated, loading, loadingMore, hasMore, onLoadMore }: { items: FeedbackItem[]; onUpdated: (feedback: FeedbackItem) => void; loading: boolean; loadingMore: boolean; hasMore: boolean; onLoadMore: () => void }) {
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<FeedbackCategory | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [status, setStatus] = useState<FeedbackStatus>("new");
  const [priority, setPriority] = useState<FeedbackPriority>("normal");
  const [adminNote, setAdminNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => items.filter((item) => (statusFilter === "all" || item.status === statusFilter) && (categoryFilter === "all" || item.category === categoryFilter) && `${item.subject} ${item.message} ${item.reporter_name} ${item.reporter_email} ${item.organization_name ?? ""}`.toLowerCase().includes(query.toLowerCase())), [categoryFilter, items, query, statusFilter]);
  const selected = filtered.find((item) => item.id === selectedId) ?? null;

  useEffect(() => {
    if (!selected && filtered[0]) setSelectedId(filtered[0].id);
  }, [filtered, selected]);
  useEffect(() => {
    if (!selected) return;
    setStatus(selected.status);
    setPriority(selected.priority);
    setAdminNote(selected.admin_note ?? "");
  }, [selected]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await updateAdminFeedback(selected.id, { status, priority, admin_note: adminNote.trim() });
      onUpdated(updated);
      toast.success("Feedback review updated.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Feedback review could not be updated.");
    } finally {
      setSaving(false);
    }
  }

  const visibleNew = items.filter((item) => item.status === "new").length;
  return <section className="feedback-admin-section">
    <div className="feedback-admin-toolbar"><div className="feedback-admin-toolbar-intro"><div><div className="eyebrow accent-eyebrow">Platform operations</div><strong>Review queue</strong><span>{visibleNew ? `${visibleNew} new signal${visibleNew === 1 ? "" : "s"} need attention` : "Everything new is up to date"}</span></div><span className="feedback-queue-count"><Inbox size={14} />{items.length} loaded</span></div><div className="feedback-filter-group"><label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as FeedbackStatus | "all")}><option value="all">All statuses</option>{statuses.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label><label>Type<select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value as FeedbackCategory | "all")}><option value="all">All types</option>{categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label><label className="feedback-search">Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Subject, reporter, organization" /></label></div></div>
    <div className="feedback-admin-layout">
      <div className="panel feedback-queue-panel"><div className="feedback-queue-head"><strong>All feedback</strong><span>{filtered.length} shown</span></div>{loading ? <div className="feedback-loading"><Clock3 size={17} />Loading feedback…</div> : filtered.length ? <><div className="feedback-queue-list">{filtered.map((item) => <button type="button" className={`feedback-queue-item ${selectedId === item.id ? "feedback-queue-item-active" : ""}`} key={item.id} onClick={() => setSelectedId(item.id)}><span className={`feedback-priority-dot feedback-priority-${item.priority}`} /><span className="feedback-queue-item-copy"><strong>{item.subject}</strong><small>{item.organization_name} · {item.reporter_name}</small><em>{categoryLabel(item.category)}</em></span><StatusPill status={item.status} /></button>)}</div>{hasMore && <button className="button button-secondary feedback-load-more" type="button" disabled={loadingMore} onClick={onLoadMore}>{loadingMore ? "Loading more…" : "Load more feedback"}</button>}</> : <div className="empty-state"><Inbox size={20} /><strong>No matching feedback</strong><span>Try another status, type, or search term.</span></div>}</div>
      <div className="panel feedback-detail-panel">{selected ? <><div className="feedback-detail-head"><div><div className="eyebrow accent-eyebrow">Review detail</div><h3>{selected.subject}</h3><p>{dateLabel(selected.created_at)}</p></div><StatusPill status={selected.status} /></div><div className="feedback-detail-meta"><div><UserRound size={15} /><span><strong>{selected.reporter_name}</strong>{selected.reporter_email}</span></div><div><Tag size={15} /><span><strong>{selected.organization_name}</strong>{categoryLabel(selected.category)}</span></div></div><div className="feedback-message"><p>{selected.message}</p>{selected.rating && <div className="feedback-readonly-rating">Rating <span>{Array.from({ length: selected.rating }, (_, index) => <Star key={index} size={14} fill="currentColor" />)}</span></div>}</div><form className="feedback-review-form" onSubmit={save}><label>Status<select value={status} onChange={(event) => setStatus(event.target.value as FeedbackStatus)}>{statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label>Priority<select value={priority} onChange={(event) => setPriority(event.target.value as FeedbackPriority)}>{priorities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label className="feedback-field-wide">Internal note<textarea value={adminNote} onChange={(event) => setAdminNote(event.target.value)} rows={4} maxLength={2000} placeholder="Add triage context for platform operations…" /><small>Only platform administrators can see this note.</small></label><div className="feedback-form-actions feedback-field-wide"><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : "Save review"}</button></div></form></> : <div className="empty-state"><MessageSquarePlus size={22} /><strong>Select a feedback item</strong><span>Choose an item from the inbox to review its details.</span></div>}</div>
    </div>
  </section>;
}

export function FeedbackPage({ isPlatformAdmin }: { isPlatformAdmin: boolean }) {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [adminItems, setAdminItems] = useState<FeedbackItem[]>([]);
  const [adminHasMore, setAdminHasMore] = useState(false);
  const [adminLoadingMore, setAdminLoadingMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [adminLoading, setAdminLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadMine() {
    try {
      setItems(await listMyFeedback());
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Your feedback history is unavailable.");
    } finally {
      setLoading(false);
    }
  }

  async function loadAdmin(append = false) {
    if (!isPlatformAdmin) return;
    if (append) setAdminLoadingMore(true);
    try {
      const pageSize = 100;
      const page = await listAdminFeedback({ limit: pageSize, offset: append ? adminItems.length : 0 });
      setAdminItems((current) => append ? [...current, ...page] : page);
      setAdminHasMore(page.length === pageSize);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The platform feedback queue is unavailable.");
    } finally {
      setAdminLoading(false);
      setAdminLoadingMore(false);
    }
  }

  useEffect(() => { if (isPlatformAdmin) { setLoading(false); void loadAdmin(); } else { void loadMine(); } }, [isPlatformAdmin]);

  function handleSubmitted(feedback: FeedbackItem) {
    if (isPlatformAdmin) void loadAdmin();
    else setItems((current) => [feedback, ...current]);
  }

  function handleUpdated(updated: FeedbackItem) {
    setAdminItems((current) => current.map((item) => item.id === updated.id ? updated : item));
  }

  return <div className="page-stack feedback-page"><PageHeader eyebrow={isPlatformAdmin ? "Platform feedback" : "Workspace feedback"} title={isPlatformAdmin ? "Feedback operations" : "Share feedback"} description={isPlatformAdmin ? "Triage feedback from end users and organization members across the platform." : "Help us improve a secure, useful workspace for your organization."} action={<div className="feedback-trust-badge"><ShieldCheck size={16} /><span><strong>Secure channel</strong><small>Tenant-aware submission</small></span></div>} />
    {error && <div className="notice notice-error"><AlertTriangle size={16} /><span>{error}</span><button type="button" onClick={() => setError("")} aria-label="Dismiss feedback error">×</button></div>}
    <div className="feedback-top-grid"><FeedbackComposer onSubmitted={handleSubmitted} /><FeedbackInsights items={isPlatformAdmin ? adminItems : items} loading={isPlatformAdmin ? adminLoading : loading} isPlatformAdmin={isPlatformAdmin} /></div>
    {isPlatformAdmin ? <AdminFeedbackQueue items={adminItems} onUpdated={handleUpdated} loading={adminLoading} loadingMore={adminLoadingMore} hasMore={adminHasMore} onLoadMore={() => void loadAdmin(true)} /> : <section aria-busy={loading}><FeedbackHistory items={items} loading={loading} onRetry={() => { setLoading(true); void loadMine(); }} /></section>}
    <div className="feedback-footer-note"><Check size={14} /><span>Feedback is handled by platform administrators. Never include passwords, access tokens, or confidential document text.</span></div>
  </div>;
}
