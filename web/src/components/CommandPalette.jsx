import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearSession } from "../api.js";

// GitLab-style global search + command palette.
// Prefixes:  >  menu items & commands   ·   :  repositories   ·   #  scan results   ·   (plain) everything.
export default function CommandPalette({ open, onClose }) {
  const nav = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [repos, setRepos] = useState([]);
  const [scans, setScans] = useState([]);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // Load searchable data whenever the palette opens.
  useEffect(() => {
    if (!open) return;
    setQuery(""); setActive(0);
    setTimeout(() => inputRef.current?.focus(), 20);
    api.listRepos().then((r) => setRepos(r.repos || [])).catch(() => {});
    api.listScans().then((r) => setScans(r.scans || [])).catch(() => {});
  }, [open]);

  function go(to, state) { onClose(); nav(to, state ? { state } : undefined); }
  function logout() { onClose(); clearSession(); nav("/login"); }

  const COMMANDS = useMemo(() => [
    { icon: "dashboard", label: "Go to Dashboard", run: () => go("/") },
    { icon: "folder_open", label: "Go to Repositories", run: () => go("/repos") },
    { icon: "science", label: "Go to Scan results", run: () => go("/scans") },
    { icon: "bolt", label: "Go to Exploit lab", run: () => go("/simulate") },
    { icon: "verified_user", label: "Go to CI security gate", run: () => go("/ci-gate") },
    { icon: "sensors", label: "Go to Monitoring", run: () => go("/monitoring") },
    { icon: "help_outline", label: "Go to How it works", run: () => go("/about") },
    { icon: "add", label: "Import a repository", run: () => go("/repos") },
    { icon: "play_arrow", label: "Run reentrancy simulation", run: () => go("/simulate", { scenario: "reentrancy", autorun: true }) },
    { icon: "play_arrow", label: "Run oracle-manipulation simulation", run: () => go("/simulate", { scenario: "oracle", autorun: true }) },
    { icon: "logout", label: "Sign out", run: logout },
  ], [repos, scans]); // eslint-disable-line

  // Build the grouped result set from the query.
  const sections = useMemo(() => {
    const raw = query.trim();
    const prefix = ">:#".includes(raw[0]) ? raw[0] : "";
    const term = (prefix ? raw.slice(1) : raw).trim().toLowerCase();
    const match = (s) => !term || (s || "").toLowerCase().includes(term);

    const cmdItems = COMMANDS.filter((c) => match(c.label))
      .map((c) => ({ icon: c.icon, label: c.label, hint: "Command", run: c.run }));
    const repoItems = repos.filter((r) => match(r.name))
      .map((r) => ({ icon: r.source_kind === "github" ? "cloud_download" : "book", label: r.name,
        hint: "Repository", run: () => go(`/repos/${r.id}`) }));
    const scanItems = scans.filter((s) => match(s.name))
      .map((s) => ({ icon: "science", label: s.name || s.id, hint: "Scan", run: () => go(`/scans/${s.id}`) }));

    if (prefix === ">") return [{ title: "Commands", items: cmdItems }];
    if (prefix === ":") return [{ title: "Repositories", items: repoItems }];
    if (prefix === "#") return [{ title: "Scan results", items: scanItems }];
    if (!term) {
      return [
        { title: "Jump to", items: cmdItems.slice(0, 7) },
        { title: "Recent repositories", items: repoItems.slice(0, 4) },
        { title: "Recent scans", items: scanItems.slice(0, 4) },
      ].filter((s) => s.items.length);
    }
    return [
      { title: "Commands", items: cmdItems },
      { title: "Repositories", items: repoItems },
      { title: "Scan results", items: scanItems },
    ].filter((s) => s.items.length);
  }, [query, repos, scans, COMMANDS]);

  const flat = useMemo(() => sections.flatMap((s) => s.items), [sections]);
  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => {
    listRef.current?.querySelector(".p-item.active")?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); flat[active]?.run(); }
  }

  let idx = -1;
  return (
    <div className="gl-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="gl-palette" role="dialog" aria-label="Command palette">
        <div className="p-input">
          <i className="material-icons">search</i>
          <input ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKey}
            placeholder="Search or go to…  (type > for commands, : repos, # scans)" />
        </div>
        <div className="p-list" ref={listRef}>
          {flat.length === 0 && <div className="p-empty">No results for “{query}”.</div>}
          {sections.map((sec) => (
            <div key={sec.title}>
              <div className="p-group">{sec.title}</div>
              {sec.items.map((it) => {
                idx += 1; const myIdx = idx;
                return (
                  <div key={sec.title + myIdx} className={`p-item ${myIdx === active ? "active" : ""}`}
                    onMouseEnter={() => setActive(myIdx)} onClick={() => it.run()}>
                    <i className="material-icons">{it.icon}</i>
                    <span className="p-label">{it.label}</span>
                    <span className="p-hint">{it.hint}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="p-footer">
          <span><kbd>↑</kbd> <kbd>↓</kbd> to navigate</span>
          <span><kbd>↵</kbd> to run</span>
          <span><kbd>esc</kbd> to close</span>
          <span style={{ marginLeft: "auto" }}><kbd>&gt;</kbd> commands · <kbd>:</kbd> repos · <kbd>#</kbd> scans</span>
        </div>
      </div>
    </div>
  );
}
