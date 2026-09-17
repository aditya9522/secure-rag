import { useState } from "react";
import type { FormEvent } from "react";
import { AlertTriangle, LockKeyhole, ShieldCheck } from "lucide-react";
import { acceptInvitation, login, type AuthResponse } from "../../lib/api";

export type AuthMode = "signin" | "invite";

export function AuthForm({ mode: initialMode = "signin", inviteToken = "", onAuthenticated }: { mode?: AuthMode; inviteToken?: string; onAuthenticated: (session: AuthResponse) => void }) {
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const session = mode === "signin"
        ? await login({ email, password })
        : await acceptInvitation({ invitation_token: inviteToken, password });
      onAuthenticated(session);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="auth-form-card">
    <div className="auth-mark"><ShieldCheck size={20} /></div>
    <div className="eyebrow accent-eyebrow">Secure access</div>
    <h2>{mode === "signin" ? "Welcome back" : "Accept invitation"}</h2>
    <p className="auth-copy">{mode === "signin" ? "Sign in to continue with your authorized organization context." : "Create your account and join the organization that invited you."}</p>
    <form className="auth-form" onSubmit={submit}>
      {mode !== "invite" && <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>}
      {mode === "invite" && <label>Invitation token<input value={inviteToken} readOnly aria-describedby="invite-help" /></label>}
      <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} autoComplete={mode === "signin" ? "current-password" : "new-password"} /></label>
      <small id="invite-help">{mode === "invite" ? "This token was issued by your organization administrator." : "Use at least 12 characters."}</small>
      <button className="password-button" disabled={busy}>{busy ? "Working…" : mode === "signin" ? "Sign in" : "Join organization"}</button>
    </form>
    <div className="auth-security"><LockKeyhole size={15} /><span>Credentials are sent only to the configured API over secure transport.</span></div>
    {notice && <div className="auth-notice" role="alert"><AlertTriangle size={14} />{notice}</div>}
    {mode === "invite" && <p className="auth-switch">Have an account? <button type="button" onClick={() => { setMode("signin"); setNotice(""); }}>Sign in</button></p>}
    {mode === "signin" && <p className="auth-switch">Organizations are managed by the platform administrator.</p>}
  </div>;
}
