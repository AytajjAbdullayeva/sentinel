import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Card, PageHeader } from "../components/ui.jsx";

export default function Diff() {
  const [scans, setScans] = useState([]);
  const [baseline, setBaseline] = useState("");
  const [name, setName] = useState("Vault");
  const [source, setSource] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listScans().then((r) => { setScans(r.scans); if (r.scans[0]) setBaseline(r.scans[0].id); });
  }, []);

  async function run() {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await api.diff(baseline, name, source, null)); }
    catch (err) { setError(err.message || "Diff failed"); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader subtitle="Operate" title="CI security gate" />
      <Card title="Compare a new version against a saved scan">
        <p className="plain-note mb-4">
          If a code change introduces (or worsens) a high-risk path, the gate fails — the same check you'd
          run automatically on every pull request.
        </p>
        <div className="row">
          <div className="col-md-6">
            <label className="text-muted" style={{ fontSize: 13 }}>Baseline scan</label>
            <select className="form-control mb-3" value={baseline} onChange={(e) => setBaseline(e.target.value)}>
              {scans.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="col-md-6">
            <label className="text-muted" style={{ fontSize: 13 }}>New version name</label>
            <input className="form-control mb-3" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <label className="text-muted" style={{ fontSize: 13 }}>New version source</label>
        <textarea className="form-control code-editor" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Paste the changed Solidity…" style={{ fontFamily: "Consolas, monospace", fontSize: 13, minHeight: 220 }} />
        <button className="btn btn-primary mt-3" onClick={run} disabled={busy || !baseline || !source}>
          {busy ? <><span className="spin" /> &nbsp;Checking…</> : <><i className="material-icons align-middle" style={{ fontSize: 18 }}>verified_user</i> Run gate</>}
        </button>
        {error && <div className="callout callout-bad mt-3">{error}</div>}
      </Card>

      {result && (
        <>
          <div className={`callout ${result.failed ? "callout-bad" : "callout-good"} mb-4`}>
            <h5 className="mb-1">
              <i className="material-icons align-middle">{result.failed ? "block" : "check_circle"}</i>{" "}
              {result.failed ? "GATE FAILED — a high-risk change was introduced" : "GATE PASSED — no new high-risk paths"}
            </h5>
            <div style={{ fontSize: 13 }}>exit code {result.exit_code} · threshold {result.threshold}</div>
          </div>
          {(result.added.length > 0 || result.raised.length > 0) && (
            <Card title="Regressions">
              <table className="table mb-0">
                <thead className="thead-light"><tr><th>Kind</th><th>Where</th><th>Severity</th><th>Evidence</th></tr></thead>
                <tbody>
                  {result.added.map((a, i) => (
                    <tr key={`a${i}`}><td><span className="badge badge-danger">NEW</span></td><td>{a.entry}</td><td>{a.impact} ({a.severity})</td><td className="evidence">{(a.evidence || []).join(" · ")}</td></tr>
                  ))}
                  {result.raised.map((r, i) => (
                    <tr key={`r${i}`}><td><span className="badge badge-warning">ROSE</span></td><td>{r.entry}</td><td>{r.from} → {r.to}</td><td className="evidence">{(r.evidence || []).join(" · ")}</td></tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
