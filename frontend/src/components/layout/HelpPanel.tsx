import { useEffect } from "react";
import { BookOpen, Check, LockKeyhole, X } from "lucide-react";

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
      <div className="help-panel-head"><div><div className="eyebrow accent-eyebrow">Workspace guide</div><h2 id="help-title">How AegisRAG works</h2></div><button className="icon-button subtle" onClick={onClose} aria-label="Close help center"><X size={17} /></button></div>
      <p className="help-intro">Use this workspace to ask questions over approved knowledge while the API enforces organization, group, and classification access.</p>
      <div className="help-list">
        <div className="help-item"><span className="help-icon"><BookOpen size={16} /></span><div><strong>Ask workspace</strong><p>Ask a specific question. Grounded answers include the source documents used.</p></div></div>
        <div className="help-item"><span className="help-icon"><LockKeyhole size={16} /></span><div><strong>Access boundaries</strong><p>Every request is checked against your current organization membership and clearance.</p></div></div>
        <div className="help-item"><span className="help-icon"><Check size={16} /></span><div><strong>Manage safely</strong><p>Administrators can invite members, scope sources, and revoke sources from the Knowledge base.</p></div></div>
      </div>
      <div className="help-panel-footer">Need deployment support? Ask your workspace administrator to verify API readiness and provider configuration.</div>
    </section>
  </div>;
}
