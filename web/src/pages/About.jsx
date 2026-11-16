import { Card, PageHeader } from "../components/ui.jsx";

const STEPS = [
  ["science", "Scan", "Upload code; see attacker-reachable paths and how serious they look."],
  ["hub", "Attack graph", "A picture of how an attacker moves through the system — every arrow backed by real evidence."],
  ["bolt", "Exploit simulation", "We execute the attack on a real EVM and show the transactions, the profit, and whether it's truly exploitable."],
  ["verified_user", "CI security gate", "Automatically blocks a code change that introduces a high-risk path."],
  ["sensors", "Monitoring", "After launch, alerts you to real on-chain changes (upgrades, new admins) that change the risk."],
];

export default function About() {
  return (
    <div>
      <PageHeader subtitle="Overview" title="How Sentinel works" />
      <div className="row">
        <div className="col-md-6">
          <Card title="The problem">
            <p className="plain-note">
              In DeFi, real losses rarely come from one obvious bug. They come from a <b>chain</b> of small,
              individually-reasonable steps that together let an attacker reach the money. Ordinary scanners
              list isolated warnings and miss the chain.
            </p>
          </Card>
        </div>
        <div className="col-md-6">
          <Card title="What Sentinel does differently">
            <p className="plain-note">
              It models the whole protocol as a graph and finds the <b>paths</b> from an attacker's entry
              point to something valuable — then <b>runs the attack on a real blockchain</b> to prove whether
              it actually works, and never shows a made-up number.
            </p>
          </Card>
        </div>
      </div>

      <Card title="What each section shows you">
        <div className="row">
          {STEPS.map(([icon, title, desc]) => (
            <div className="col-md-6 mb-3 d-flex" key={title}>
              <i className="material-icons text-primary mr-3" style={{ fontSize: 30 }}>{icon}</i>
              <div>
                <div className="font-weight-bold">{title}</div>
                <div className="text-muted" style={{ fontSize: 14 }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Our promise">
        <p className="plain-note">
          Every number you see traces to a specific source — a line of code, a real on-chain read, or a
          declared assumption clearly marked as such. When something can't be determined, Sentinel says
          <b> “unknown”</b> instead of inventing a value.
        </p>
      </Card>
    </div>
  );
}
