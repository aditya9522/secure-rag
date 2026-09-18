import { useEffect } from "react";
import { BookOpen, Check, ChevronRight, FileText, KeyRound, Layers3, LockKeyhole, ShieldCheck, Users, X } from "lucide-react";
import { classificationGuidance, groupGuidance, roleGuidance } from "../../data/accessGuidance";

export function HelpPanel({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", dismissOnEscape);
    return () => document.removeEventListener("keydown", dismissOnEscape);
  }, [onClose]);
  return <div className="help-overlay" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="help-panel" role="dialog" aria-modal="true" aria-labelledby="help-title">
      <div className="help-panel-head"><div className="help-brand"><span className="help-brand-icon"><BookOpen size={17} /></span><div><div className="eyebrow accent-eyebrow">Workspace guide</div><h2 id="help-title">Operate AegisRAG with confidence</h2></div></div><button className="icon-button subtle" onClick={onClose} aria-label="Close help center"><X size={17} /></button></div>
      <p className="help-intro">This guide explains how sources, classifications, groups, and member roles work together so every answer stays inside the right access boundary.</p>

      <section className="help-section">
        <div className="help-section-heading"><span className="help-section-number">01</span><div><h3>Add a governed source</h3><p>Use this flow when you want approved documents to become searchable.</p></div></div>
        <div className="help-steps"><div><span className="help-step-icon"><FileText size={14} /></span><div><strong>Choose a source</strong><p>Upload a supported PDF, DOCX, TXT, Markdown, CSV, or JSON file. Add a source URI when the file also has a canonical location.</p></div></div><div><span className="help-step-icon"><Layers3 size={14} /></span><div><strong>Set classification</strong><p>Choose the highest sensitivity level that accurately describes the document. When unsure, stop and confirm with your organization administrator.</p></div></div><div><span className="help-step-icon"><Users size={14} /></span><div><strong>Scope by group</strong><p>Add groups when only selected teams should retrieve the source. Empty groups means all members who meet the classification requirement.</p></div></div><div><span className="help-step-icon"><ShieldCheck size={14} /></span><div><strong>Verify indexing</strong><p>Wait for the source to become Active. Failed sources can be retried from the source row after correcting the file or provider issue.</p></div></div></div>
      </section>

      <section className="help-section">
        <div className="help-section-heading"><span className="help-section-number">02</span><div><h3>Classification reference</h3><p>Classification controls the minimum clearance a member needs before group checks are considered.</p></div></div>
        <div className="help-classification-grid">{classificationGuidance.map((item) => <article className="help-classification-card" key={item.value}><div className={`classification-mark classification-${item.value}`}><KeyRound size={13} /></div><div><strong>{item.label}</strong><span>{item.summary}</span><p>{item.useCase}</p><small>Example: {item.example}</small></div></article>)}</div>
      </section>

      <section className="help-section help-access-section">
        <div className="help-section-heading"><span className="help-section-number">03</span><div><h3>How access groups work</h3><p>{groupGuidance.summary}</p></div></div>
        <div className="help-callout"><Users size={16} /><div><strong>Think of access as two checks</strong><p>{groupGuidance.useCase} The member must have sufficient classification clearance <em>and</em> belong to one of the source’s allowed groups.</p><div className="guide-chip-row">{groupGuidance.examples.map((group) => <span key={group}>{group}</span>)}</div><small>{groupGuidance.empty}</small></div></div>
      </section>

      <section className="help-section">
        <div className="help-section-heading"><span className="help-section-number">04</span><div><h3>Invite and manage members</h3><p>Invite people with the smallest role and clearance they need to do their work.</p></div></div>
        <div className="help-steps help-member-steps"><div><span className="help-step-icon"><Users size={14} /></span><div><strong>Invite with a verified email</strong><p>Enter the person’s name and work email. The invitation link is shown once and should be shared through a trusted channel.</p></div></div><div><span className="help-step-icon"><LockKeyhole size={14} /></span><div><strong>Choose role and clearance</strong><p>Use Member for normal workspace use. Grant Administrator only to trusted operators who need to manage sources and access.</p></div></div><div><span className="help-step-icon"><Check size={14} /></span><div><strong>Add team groups</strong><p>Match group names to the groups used on your sources, such as engineering or support. Members need both the right group and clearance.</p></div></div></div>
        <div className="help-role-grid"><article><strong>Member</strong><p>{roleGuidance.member}</p></article><article><strong>Administrator</strong><p>{roleGuidance.admin}</p></article></div>
      </section>

      <div className="help-panel-footer"><ChevronRight size={14} /><span>Need deployment support? Ask your platform administrator to verify API readiness, database migrations, provider configuration, and source indexing.</span></div>
    </section>
  </div>;
}
