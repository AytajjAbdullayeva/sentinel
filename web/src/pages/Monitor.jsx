import { useState } from "react";
import { api } from "../api.js";
import { Card, PageHeader } from "../components/ui.jsx";

const KIND = {
  implementation_upgraded: ["Contract logic upgraded", "upgrade"],
  proxy_admin_changed: ["Proxy admin changed", "admin_panel_settings"],
  owner_changed: ["Ownership transferred", "swap_horiz"],
  role_granted: ["Privileged role granted", "person_add"],
  role_revoked: ["Privileged role revoked", "person_remove"],
};

export default function Monitor() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await api.monitorDemo()); }
    catch (err) { setError(err.message || "Monitor failed"); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader subtitle="Operate" title="Monitoring" />
      <Card title="Watch the chain for attack-surface changes">
        <p className="plain-note mb-4">
          After deployment a protocol keeps changing — upgrades, new admins, role grants. Sentinel reports
          only <b>real</b> on-chain events. This demo performs a real upgrade and a real role grant on a
          local chain, then shows what the monitor detected.
        </p>
        <button className="btn btn-primary" onClick={run} disabled={busy}>
          {busy ? <><span className="spin" /> &nbsp;Running on real EVM…</> : <><i className="material-icons align-middle" style={{ fontSize: 18 }}>sensors</i> Run live monitoring demo</>}
        </button>
        {error && <div className="callout callout-bad mt-3">{error}</div>}
      </Card>

      {result && (
        <>
          <div className="callout callout-good mb-4">
            <i className="material-icons align-middle">check_circle</i> Baseline at block {result.baseline_block}.
            A quiet poll (no change) reported <b>{result.quiet_poll.length}</b> events — proof it doesn't invent drift.
          </div>
          <Card title="Detected changes (from real chain events)">
            <table className="table mb-0">
              <thead className="thead-light"><tr><th>Event</th><th>Where</th><th>Before → After</th><th>Tx hash</th></tr></thead>
              <tbody>
                {result.drift.map((d, i) => {
                  const [label, icon] = KIND[d.kind] || [d.kind, "bolt"];
                  return (
                    <tr key={i}>
                      <td><i className="material-icons align-middle text-warning mr-1" style={{ fontSize: 18 }}>{icon}</i><b>{label}</b></td>
                      <td className="mono">{d.address}</td>
                      <td className="mono">{(d.before || "—")} → {(d.after || "—")}</td>
                      <td className="mono">{d.evidence?.tx_hash}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
