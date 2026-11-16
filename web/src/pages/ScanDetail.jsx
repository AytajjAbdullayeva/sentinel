import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import cytoscape from "cytoscape";
import { api } from "../api.js";
import { Card, Empty, ErrorNote, Loading, PageHeader, riskWord, severityBadge } from "../components/ui.jsx";

// Which recognised patterns Sentinel can prove on a real EVM today.
const PROVABLE = { reentrancy: "reentrancy", oracle_manipulation: "oracle" };

const NODE_COLORS = {
  actor: "#c4183c", authority: "#ffb400", contract: "#5a6b86", function: "#007bff", asset: "#17c671",
};
const TABS = [["overview", "Overview", "insights"], ["findings", "Findings", "list"],
  ["graph", "Attack graph", "hub"], ["narrative", "Explanation", "notes"]];

export default function ScanDetail() {
  const { id } = useParams();
  const [tab, setTab] = useState("overview");
  const [scan, setScan] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.getScan(id).then(setScan).catch(setError); }, [id]);
  if (error) return <ErrorNote error={error} />;
  if (!scan) return <Loading />;

  return (
    <div>
      <PageHeader subtitle="Scan" title={scan.name} />
      <div className="mb-3 text-muted" style={{ fontSize: 13 }}>
        Compiler <span className="mono">{scan.compiler}</span> · {scan.contracts} contract(s) · {scan.facts} facts · top severity {severityBadge(scan.max_severity || 0)}
      </div>

      <ul className="nav nav-tabs mb-4">
        {TABS.map(([t, label, icon]) => (
          <li className="nav-item" key={t}>
            <button className={`nav-link ${tab === t ? "active" : ""}`} onClick={() => setTab(t)} style={{ border: "none", background: "none" }}>
              <i className="material-icons align-middle" style={{ fontSize: 17 }}>{icon}</i> {label}
            </button>
          </li>
        ))}
      </ul>

      {tab === "overview" && <Overview scan={scan} />}
      {tab === "findings" && <Findings scan={scan} />}
      {tab === "graph" && <GraphTab id={id} />}
      {tab === "narrative" && <NarrativeTab id={id} />}
    </div>
  );
}

function Overview({ scan }) {
  const f = scan.findings || [];
  const worst = Math.max(0, ...f.map((x) => x.severity_score || 0));
  const patterns = [...new Set(f.map((x) => x.pattern).filter(Boolean))];
  return (
    <div className="row">
      <div className="col-lg-7">
        <Card title="What this means">
          <p className="plain-note">
            Sentinel found <b>{f.length}</b> attacker-reachable path(s) in <b>{scan.name}</b>. The most
            serious is <b>{riskWord(worst)}</b>. A path is a chain of steps an attacker could follow from an
            entry point to something valuable. Severity is the analyzer's own label; whether a path is truly
            exploitable is confirmed by running it on a real EVM (see Exploit simulation).
          </p>
        </Card>
      </div>
      <div className="col-lg-5">
        <Card title="At a glance">
          <table className="table table-sm mb-0">
            <tbody>
              <tr><td className="text-muted">Attacker-reachable paths</td><td className="text-right font-weight-bold">{f.length}</td></tr>
              <tr><td className="text-muted">Highest severity</td><td className="text-right">{severityBadge(worst)}</td></tr>
              <tr><td className="text-muted">Patterns</td><td className="text-right">{patterns.join(", ") || "—"}</td></tr>
              <tr><td className="text-muted">Compiler</td><td className="text-right mono">{scan.compiler}</td></tr>
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}

function Findings({ scan }) {
  const f = scan.findings || [];
  const [proof, setProof] = useState({}); // pattern -> {busy, result, error}

  async function prove(pattern) {
    const scenario = PROVABLE[pattern];
    setProof((p) => ({ ...p, [pattern]: { busy: true } }));
    try {
      const r = await api.simulate(scenario, false, "2500");
      setProof((p) => ({ ...p, [pattern]: { result: r } }));
    } catch (err) {
      setProof((p) => ({ ...p, [pattern]: { error: err.message } }));
    }
  }

  if (!f.length) return <Card><Empty icon="verified_user">No attacker-reachable paths found.</Empty></Card>;
  return (
    <Card title="Attack paths">
      <table className="table">
        <thead className="thead-light">
          <tr><th>Severity</th><th>Entry point</th><th>Reaches</th><th>Pattern</th><th>Evidence</th><th></th></tr>
        </thead>
        <tbody>
          {f.map((x) => {
            const scenario = PROVABLE[x.pattern];
            const st = scenario ? proof[x.pattern] : null;
            return (
              <tr key={x.stable_id}>
                <td>{severityBadge(x.severity_score || 0)}</td>
                <td className="font-weight-bold">{x.entry}</td>
                <td>{x.sink}</td>
                <td>{x.pattern ? <span className="badge badge-light">{x.pattern}</span> : "—"}</td>
                <td className="evidence">{(x.evidence || []).join("  ·  ") || "—"}</td>
                <td className="text-right">
                  {scenario && (
                    <button className="btn btn-outline-primary btn-sm" onClick={() => prove(x.pattern)} disabled={st?.busy}>
                      {st?.busy ? <span className="spin" /> : <><i className="material-icons align-middle" style={{ fontSize: 15 }}>bolt</i> Prove</>}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {Object.entries(proof).map(([pattern, st]) => (
        st?.result && (
          <div key={pattern} className={`callout ${st.result.feasible ? "callout-bad" : "callout-good"} mt-2`}>
            <b><i className="material-icons align-middle">{st.result.feasible ? "gpp_bad" : "gpp_good"}</i>{" "}
              Proof ({pattern}): {st.result.feasible ? `exploitable on a real EVM — attacker profits ${st.result.profit_eth.toFixed(2)} ETH` : "not exploitable"}</b>
            <div style={{ fontSize: 13 }}>{st.result.steps.length} real transactions executed · see <Link to="/simulate">Exploit lab</Link> for full receipts.</div>
          </div>
        )
      ))}
      <p className="plain-note mt-2">
        “Prove” runs a faithful reproduction of the pattern on a real local blockchain and reports whether
        the attack truly succeeds — turning a static warning into on-chain evidence.
      </p>
    </Card>
  );
}

function GraphTab({ id }) {
  const ref = useRef(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let cy;
    api.graph(id).then((g) => {
      cy = cytoscape({
        container: ref.current,
        elements: [...g.nodes, ...g.edges],
        style: [
          { selector: "node", style: {
              "background-color": (n) => NODE_COLORS[n.data("ntype")] || "#818ea3",
              label: "data(label)", color: "#3d5170", "font-size": 10, "text-wrap": "wrap",
              "text-max-width": 130, "text-valign": "bottom", "text-margin-y": 5, width: 24, height: 24 } },
          { selector: "edge", style: {
              width: 2, "line-color": "#c3ccda", "target-arrow-color": "#c3ccda",
              "target-arrow-shape": "triangle", "curve-style": "bezier",
              label: "data(label)", "font-size": 8, color: "#a7b0bd" } },
        ],
        layout: { name: "breadthfirst", directed: true, spacingFactor: 1.35, padding: 20 },
      });
    }).catch(setError);
    return () => cy && cy.destroy();
  }, [id]);
  const legend = [["actor", "attacker"], ["function", "function"], ["asset", "asset"], ["authority", "authority"], ["contract", "contract"]];
  return (
    <Card title="Attack graph" actions={
      <div style={{ fontSize: 12 }} className="text-muted">
        {legend.map(([k, l]) => (<span key={k} className="mr-2"><span className="legend-dot" style={{ background: NODE_COLORS[k] }} />{l}</span>))}
      </div>
    }>
      <ErrorNote error={error} />
      <div id="cy" ref={ref} />
      <p className="plain-note mt-3">Each arrow is backed by a real fact from the compiler or analyzer — there are no invented links.</p>
    </Card>
  );
}

function NarrativeTab({ id }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api.narratives(id).then((r) => setData(r.narratives)).catch(setError); }, [id]);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  if (!data.length) return <Card><Empty icon="notes">No explanation (no attacker-reachable path).</Empty></Card>;
  return (
    <>
      {data.map((n, i) => (
        <Card key={i} title={`Explanation ${i + 1}: ${n.target}`}>
          <ul className="list-unstyled mb-0">
            {n.claims.map((c, j) => (
              <li key={j} className="mb-3">
                <i className="material-icons align-middle text-success" style={{ fontSize: 18 }}>check_circle</i> {c.text}
                <div className="evidence ml-4">evidence: {c.evidence.join(", ")}</div>
              </li>
            ))}
          </ul>
          {n.removed?.length > 0 && (
            <div className="text-muted mt-2" style={{ fontSize: 12 }}>
              <i className="material-icons align-middle" style={{ fontSize: 15 }}>block</i> {n.removed.length} unsupported claim(s) removed as ungrounded.
            </div>
          )}
        </Card>
      ))}
    </>
  );
}
