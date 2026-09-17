import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { onSessionExpired, refreshSession, type AuthResponse } from "./lib/api";
import { AuthPage } from "./features/auth/AuthPage";
import { AuthenticatedWorkspace } from "./app/AuthenticatedWorkspace";
import { Toaster } from "react-hot-toast";

function App() {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [startupError, setStartupError] = useState("");

  const checkSession = useCallback(async () => {
    setAuthChecked(false);
    setStartupError("");
    try {
      setSession(await refreshSession());
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      if (message === "API is not configured. Set VITE_API_BASE_URL." || error instanceof TypeError) {
        setStartupError("The secure API could not be reached. Configure VITE_API_BASE_URL and verify the API allows this site in its CORS settings.");
      }
    } finally {
      setAuthChecked(true);
    }
  }, []);

  useEffect(() => { void checkSession(); }, [checkSession]);

  useEffect(() => {
    onSessionExpired(() => setSession(null));
    return () => onSessionExpired(null);
  }, []);

  const content = !authChecked
    ? <div className="auth-loading" role="status">Checking your secure session…</div>
    : startupError
      ? <main className="auth-page"><section className="auth-page-panel"><div className="auth-form-card" role="alert"><div className="eyebrow accent-eyebrow">Setup required</div><h2>Workspace unavailable</h2><p className="auth-copy">{startupError}</p><button className="password-button" type="button" onClick={() => void checkSession()}>Try again</button></div></section></main>
    : !session
      ? <AuthPage onAuthenticated={setSession} />
      : <AuthenticatedWorkspace session={session} onSessionUpdated={setSession} onSignedOut={() => setSession(null)} />;

  return <><Toaster position="top-right" toastOptions={{ duration: 4000 }} />{content}</>;
}

export default App;
