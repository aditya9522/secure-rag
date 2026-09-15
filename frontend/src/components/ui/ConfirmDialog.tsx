import { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";

export function ConfirmDialog({ title, description, confirmLabel = "Confirm", busy = false, onConfirm, onCancel }: { title: string; description: string; confirmLabel?: string; busy?: boolean; onConfirm: () => void; onCancel: () => void }) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onCancel();
    }
    document.addEventListener("keydown", dismissOnEscape);
    return () => document.removeEventListener("keydown", dismissOnEscape);
  }, [busy, onCancel]);

  return <div className="modal-backdrop" role="presentation" onPointerDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
    <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-description">
      <button className="icon-button subtle confirm-close" type="button" onClick={onCancel} disabled={busy} aria-label="Close confirmation"><X size={17} /></button>
      <div className="confirm-icon"><AlertTriangle size={18} /></div>
      <h2 id="confirm-title">{title}</h2>
      <p id="confirm-description">{description}</p>
      <div className="confirm-actions"><button ref={cancelRef} className="button button-secondary" type="button" onClick={onCancel} disabled={busy}>Cancel</button><button className="button button-danger" type="button" onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button></div>
    </section>
  </div>;
}
