import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Card, Empty, ErrorNote, Loading, PageHeader, riskWord, severityBadge } from "../components/ui.jsx";

export default function Scans() {
  const [scans, setScans] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.listScans().then((r) => setScans(r.scans)).catch(setError);
  }, []);
  if (error) return <ErrorNote error={error} />;
  if (!scans) return <Loading />;
  return (
    <div>
      <PageHeader
        subtitle="Analyze"
        title="Scans"
        actions={<Link className="btn btn-primary" to="/repos"><i className="material-icons align-middle" style={{ fontSize: 18 }}>folder_open</i> Repositories</Link>}
      />
      <Card>
        {scans.length === 0 ? (
          <Empty icon="science">No scans yet.</Empty>
        ) : (
          <table className="table mb-0">
            <thead className="thead-light">
              <tr><th>Name</th><th>Compiler</th><th>Contracts</th><th>Paths</th><th>Risk</th><th></th></tr>
            </thead>
            <tbody>
              {scans.map((s) => (
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
