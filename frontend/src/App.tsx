import { useEffect, useState } from "react";
import "./App.css";
import { onSessionExpired, refreshSession, type AuthResponse } from "./lib/api";
import { AuthPage } from "./features/auth/AuthPage";
import { AuthenticatedWorkspace } from "./app/AuthenticatedWorkspace";
import { Toaster } from "react-hot-toast";

function App() {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    void refreshSession()
      .then(setSession)
      .catch(() => undefined)
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    onSessionExpired(() => setSession(null));
    return () => onSessionExpired(null);
  }, []);

  const content = !authChecked
    ? <div className="auth-loading" role="status">Checking your secure session…</div>
    : !session
      ? <AuthPage onAuthenticated={setSession} />
      : <AuthenticatedWorkspace session={session} onSessionUpdated={setSession} onSignedOut={() => setSession(null)} />;

  return <><Toaster position="top-right" toastOptions={{ duration: 4000 }} />{content}</>;
}

export default App;
