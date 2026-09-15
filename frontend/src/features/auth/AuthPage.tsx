import { Database, LockKeyhole, ShieldCheck, Users } from "lucide-react";
import type { AuthResponse } from "../../lib/api";
import { AuthForm, type AuthMode } from "./AuthForm";

export function AuthPage({ onAuthenticated }: { onAuthenticated: (session: AuthResponse) => void }) {
  const inviteToken = new URLSearchParams(window.location.search).get("invite") ?? "";
  const mode: AuthMode = inviteToken ? "invite" : "signin";
  return <main className="auth-page"><section className="auth-page-intro"><div className="brand-row auth-page-brand"><div className="brand-mark"><ShieldCheck size={19} strokeWidth={2.5} /></div><span className="brand-name">Aegis<span>RAG</span></span></div><div className="auth-page-copy"><div className="eyebrow accent-eyebrow">Private knowledge, safely answered</div><h1>Your organization’s secure AI workspace.</h1><p>Ask questions across approved knowledge sources with tenant isolation, access-aware retrieval, and traceable answers.</p><div className="auth-benefits"><span><ShieldCheck size={16} /> Tenant-isolated answers</span><span><LockKeyhole size={16} /> Access checked every request</span><span><Database size={16} /> Source-grounded citations</span><span><Users size={16} /> Multiple organizations supported</span></div></div><small className="auth-page-footer">Protected by deterministic authorization. The model never decides what you can access.</small></section><section className="auth-page-panel"><AuthForm mode={mode} inviteToken={inviteToken} onAuthenticated={onAuthenticated} /></section></main>;
}
