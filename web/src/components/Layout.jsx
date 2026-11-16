import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSession, session } from "../api.js";
import CommandPalette from "./CommandPalette.jsx";

const NAV = [
  { group: "Pinned", items: [
    ["/", "Dashboard", "dashboard"],
    ["/repos", "Repositories", "folder_open"],
  ] },
  { group: "Analyze", items: [
    ["/scans", "Scan results", "science"],
  ] },
  { group: "Secure", items: [
    ["/simulate", "Exploit lab", "bolt"],
    ["/ci-gate", "CI security gate", "verified_user"],
    ["/monitoring", "Monitoring", "sensors"],
  ] },
  { group: "Help", items: [
    ["/about", "How it works", "help_outline"],
  ] },
];

export default function Layout() {
  const nav = useNavigate();
  const s = session();
  const [open, setOpen] = useState(false);       // mobile sidebar
  const [palette, setPalette] = useState(false); // command palette

  // Global shortcuts: "/" and Cmd/Ctrl-K open the palette (GitLab behaviour).
  useEffect(() => {
    function onKey(e) {
      const el = document.activeElement;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { e.preventDefault(); setPalette(true); }
      else if (e.key === "/" && !typing && !palette) { e.preventDefault(); setPalette(true); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [palette]);

  function logout() { clearSession(); nav("/login"); }
  const org = (s.org || "").slice(0, 8);

  return (
    <div className="gl-shell">
      <aside className={`gl-sidebar ${open ? "open" : ""}`}>
        <NavLink to="/" className="gl-context" onClick={() => setOpen(false)}>
          <div className="gl-logo">S</div>
          <div>
            <div className="nm">Sentinel</div>
            <div className="sub">{org || "workspace"} · {s.role}</div>
          </div>
        </NavLink>

        <div className="gl-search">
          <button onClick={() => setPalette(true)}>
            <i className="material-icons">search</i>
            Search or go to…
            <span className="kbd">/</span>
          </button>
        </div>

        <nav className="gl-nav" onClick={() => setOpen(false)}>
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="gl-navgroup">{g.group}</div>
              {g.items.map(([to, label, icon]) => (
                <NavLink key={to} to={to} end={to === "/"}>
                  <i className="material-icons">{icon}</i>{label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="gl-user">
          <div className="gl-avatar">{(s.role || "?")[0].toUpperCase()}</div>
          <div className="who">
            <div className="nm">{s.role || "user"}</div>
            <div className="sub">{org}</div>
          </div>
          <button className="btn btn-white btn-sm" onClick={logout} title="Sign out">
            <i className="material-icons" style={{ fontSize: 16 }}>logout</i>
          </button>
        </div>
      </aside>

      <div className="gl-main">
        <div className="gl-topbar">
          <button className="gl-burger" onClick={() => setOpen((o) => !o)}>
            <i className="material-icons">menu</i>
          </button>
          <div className="gl-logo" style={{ width: 26, height: 26, fontSize: 14 }}>S</div>
          <b>Sentinel</b>
          <button className="btn btn-white btn-sm" style={{ marginLeft: "auto" }} onClick={() => setPalette(true)}>
            <i className="material-icons" style={{ fontSize: 16 }}>search</i>
          </button>
        </div>
        <main className="gl-content">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}
