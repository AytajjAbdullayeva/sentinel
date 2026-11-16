import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api.js";
import { Card, PageHeader } from "../components/ui.jsx";

export default function Simulate() {
  const loc = useLocation();
  const [scenario, setScenario] = useState(loc.state?.scenario || "reentrancy");
  const [patched, setPatched] = useState(false);
  const [price, setPrice] = useState("2500");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await api.simulate(scenario, patched, price || null)); }
    catch (err) { setError(err.message || "Simulation failed"); }
    finally { setBusy(false); }
  }

  const ranOnce = useRef(false);
  useEffect(() => {
    if (loc.state?.autorun && !ranOnce.current) { ranOnce.current = true; run(); }
  }, []); // eslint-disable-line

  return (
    <div>
      <PageHeader subtitle="Tools" title="Exploit lab" />
      <Card title="Prove an attack on a real local blockchain">
        <p className="plain-note mb-4">
          The lab takes a faithful reproduction of a known DeFi attack pattern, deploys it to a real local
          EVM (Anvil) and <b>actually executes the exploit</b>. “Exploitable” means the transactions really
          succeeded and the attacker's balance really grew — read from the actual receipts, not guessed.
          This is what backs the <b>Prove</b> button on a scan's findings.
        </p>
        <div className="row">
          <div className="col-md-4">
            <label className="text-muted" style={{ fontSize: 13 }}>Scenario</label>
            <select className="form-control" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="reentrancy">Reentrancy (fund-draining)</option>
              <option value="oracle">Oracle price manipulation</option>
            </select>
          </div>
          <div className="col-md-4">
            <label className="text-muted" style={{ fontSize: 13 }}>Version</label>
            <select className="form-control" value={patched ? "patched" : "vuln"} onChange={(e) => setPatched(e.target.value === "patched")}>
              <option value="vuln">Vulnerable</option>
              <option value="patched">Patched (fixed)</option>
            </select>
          </div>
          <div className="col-md-4">
            <label className="text-muted" style={{ fontSize: 13 }}>ETH price (USD, declared)</label>
            <input className="form-control" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 2500" />
          </div>
        </div>
        <button className="btn btn-primary mt-3" onClick={run} disabled={busy}>
          {busy ? <><span className="spin" /> &nbsp;Running on real EVM…</> : <><i className="material-icons align-middle" style={{ fontSize: 18 }}>bolt</i> Run simulation</>}
        </button>
        {error && <div className="callout callout-bad mt-3">{error}</div>}
      </Card>

      {result && (
        <>
          <div className={`callout ${result.feasible ? "callout-bad" : "callout-good"} mb-4`}>
            <h5 className="mb-1">
              <i className="material-icons align-middle">{result.feasible ? "gpp_bad" : "gpp_good"}</i>{" "}
              {result.feasible ? `Exploitable — attacker profits ${result.profit_eth.toFixed(2)} ETH` : "Not exploitable — the attack reverted on-chain"}
            </h5>
            <div style={{ fontSize: 13 }}>{result.reason}</div>
          </div>

          <Card title="Transactions executed (real receipts)">
            <table className="table mb-0">
              <thead className="thead-light"><tr><th>Step</th><th>Result</th><th>Gas</th><th>Tx hash</th></tr></thead>
              <tbody>
                {result.steps.map((s, i) => (
                  <tr key={i}>
                    <td>{s.description}</td>
                    <td>{s.status === 1 ? <span className="badge badge-success">OK</span> : <span className="badge badge-danger">REVERT</span>}</td>
                    <td>{s.gas_used ?? "—"}</td>
                    <td className="mono">{s.tx_hash || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {result.score && (
            <Card title={`Risk score: ${result.score.status === "scored" ? result.score.score.toFixed(2) : result.score.status}`}>
              {result.score.status === "scored" ? (
                <table className="table table-sm mb-0">
                  <thead className="thead-light"><tr><th>Component</th><th>Value</th><th>Where it came from</th></tr></thead>
                  <tbody>
                    {Object.entries(result.score.components).map(([k, c]) => (
                      <tr key={k}><td className="font-weight-bold">{k}</td><td>{c.value.toFixed(4)}</td><td className="evidence">{c.origin}</td></tr>
                    ))}
                  </tbody>
                </table>
              ) : <p className="plain-note">{result.score.reason}</p>}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
