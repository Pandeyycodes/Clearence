"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("recruiter@clearance.local");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.message ?? "Login failed.");
      setBusy(false);
    }
  };

  return (
    <main>
      <div className="card" style={{ maxWidth: 460, margin: "0 auto" }}>
        <h2>Sign in</h2>
        <p className="hint" style={{ marginBottom: 18 }}>
          Clearance is access-controlled: every screening is recorded against
          the recruiter who ran it.
        </p>
        <form onSubmit={submit}>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" value={email} required
            onChange={(e) => setEmail(e.target.value)} />
          <label className="label" htmlFor="password"
            style={{ marginTop: 12, display: "block" }}>Password</label>
          <input id="password" type="password" value={password} required
            onChange={(e) => setPassword(e.target.value)} />
          <div style={{ marginTop: 16 }}>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </div>
        </form>
        {error && <div className="error-note">{error}</div>}
        <p className="hint" style={{ marginTop: 18 }}>
          Demo login: <span className="mono">recruiter@clearance.local</span> /
          <span className="mono"> demo1234</span>
        </p>
      </div>
    </main>
  );
}
