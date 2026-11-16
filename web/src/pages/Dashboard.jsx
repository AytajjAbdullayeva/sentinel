import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Card, Empty, ErrorNote, Loading, PageHeader, StatCard, riskWord, severityBadge } from "../components/ui.jsx";

export default function Dashboard() {
  const [scans, setScans] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listScans().then((r) => setScans(r.scans)).catch(setError);
  }, []);

  if (error) return <ErrorNote error={error} />;
  if (!scans) return <Loading />;

  const totalFindings = scans.reduce((a, s) => a + (s.findings || 0), 0);
  const highScans = scans.filter((s) => (s.max_severity || 0) >= 80).length;

  return (
    <div>
      <PageHeader
        subtitle="Overview"
        title="Security dashboard"
        actions={<Link className="btn btn-primary" to="/repos"><i className="material-icons align-middle" style={{ fontSize: 18 }}>folder_open</i> Repositories</Link>}
      />

      <div className="row">
        <div className="col-lg-3 col-md-6 mb-4"><StatCard label="Protocols scanned" value={scans.length} hint="source contracts analysed" icon="science" accent="primary" /></div>
        <div className="col-lg-3 col-md-6 mb-4"><StatCard label="Attacker paths" value={totalFindings} hint="ways in found" icon="alt_route" accent="info" /></div>
        <div className="col-lg-3 col-md-6 mb-4"><StatCard label="High-severity scans" value={highScans} hint="need attention first" icon="priority_high" accent="danger" /></div>
        <div className="col-lg-3 col-md-6 mb-4"><StatCard label="Verified by" value="real EVM" hint="feasibility from live simulation" icon="verified" accent="success" /></div>
      </div>

      <Card title="Recent scans" actions={<Link to="/scans" className="text-muted" style={{ fontSize: 13 }}>View all →</Link>}>
        {scans.length === 0 ? (
          <Empty icon="science">No scans yet. Start by <Link to="/repos">importing a repository</Link>.</Empty>
        ) : (
          <table className="table mb-0">
            <thead className="thead-light">
              <tr><th>Name</th><th>Compiler</th><th>Contracts</th><th>Paths</th><th>Top severity</th><th></th></tr>
            </thead>
            <tbody>
              {scans.slice(0, 8).map((s) => (
                <tr key={s.id}>
                  <td className="font-weight-bold">{s.name}</td>
                  <td className="mono text-muted">{s.compiler}</td>
                  <td>{s.contracts}</td>
                  <td>{s.findings}</td>
                  <td>{severityBadge(s.max_severity || 0)} <small className="text-muted ml-1">{riskWord(s.max_severity || 0)}</small></td>
                  <td className="text-right"><Link to={`/scans/${s.id}`}>Open →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
