// Shared presentational helpers, styled with shards-ui / Bootstrap 4 classes.

export function severityBadge(score) {
  if (score >= 80) return <span className="badge badge-danger">HIGH</span>;
  if (score >= 50) return <span className="badge badge-warning">MEDIUM</span>;
  if (score >= 20) return <span className="badge badge-info">LOW</span>;
  return <span className="badge badge-secondary">INFO</span>;
}

export function riskWord(score) {
  if (score >= 80) return "Critical risk";
  if (score >= 50) return "Elevated risk";
  if (score >= 20) return "Low risk";
  return "Informational";
}

export function PageHeader({ subtitle, title, actions }) {
  return (
    <div className="page-header d-flex align-items-end justify-content-between flex-wrap">
      <div>
        <div className="subtitle">{subtitle}</div>
        <h3>{title}</h3>
      </div>
      {actions}
    </div>
  );
}

export function StatCard({ label, value, hint, icon, accent }) {
  return (
    <div className={`card card-small stat-card ${accent ? "accent-" + accent : ""}`}>
      <div className="card-body">
        {icon && <i className="material-icons stat-icon">{icon}</i>}
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </div>
  );
}

export function Card({ title, children, actions }) {
  return (
    <div className="card card-small mb-4">
      {title && (
        <div className="card-header border-bottom d-flex align-items-center justify-content-between">
          <h6 className="m-0">{title}</h6>
          {actions}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return (
    <div className="text-muted p-3">
      <span className="spin" /> &nbsp; {label}
    </div>
  );
}

export function Empty({ icon = "inbox", children }) {
  return (
    <div className="empty-state">
      <i className="material-icons">{icon}</i>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return <div className="callout callout-bad mt-3">{error.message || String(error)}</div>;
}
