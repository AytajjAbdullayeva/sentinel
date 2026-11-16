import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setSession } from "../api.js";

export default function Login() {
  const nav = useNavigate();
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("sentinel-demo");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.login(username, password);
      setSession(r.access_token, r.org_id, r.role);
      nav("/");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="gl-login">
      <div className="box">
        <div className="text-center mb-4">
          <div className="gl-logo" style={{ width: 52, height: 52, fontSize: 26, margin: "0 auto" }}>S</div>
          <h3 className="mt-3 mb-1">Sentinel</h3>
          <div className="text-muted" style={{ fontSize: 13 }}>Attack-Path Intelligence for Solidity protocols</div>
        </div>
        <div className="card">
          <div className="card-body">
            <form onSubmit={submit}>
              <label style={{ fontSize: 13 }}>Username</label>
              <input className="form-control mb-3" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
              <label style={{ fontSize: 13 }}>Password</label>
              <input className="form-control mb-3" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <button className="btn btn-primary btn-block" disabled={busy}>
                {busy ? <><span className="spin" /> &nbsp;Signing in…</> : "Sign in"}
              </button>
            </form>
            {error && <div className="callout callout-bad mt-3">{error}</div>}
          </div>
        </div>
        <p className="text-muted text-center mt-3 mb-0" style={{ fontSize: 12 }}>
          Demo accounts: admin · analyst · viewer &nbsp;·&nbsp; password <b>sentinel-demo</b>
        </p>
      </div>
    </div>
  );
}
