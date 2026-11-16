import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Card, Empty, ErrorNote, Loading, PageHeader } from "../components/ui.jsx";

export default function Repos() {
  const [repos, setRepos] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("github");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState(null);

  function load() {
    api.listRepos().then((r) => setRepos(r.repos)).catch(setError);
  }
  useEffect(load, []);

  async function create() {
    setBusy(true);
    setFormErr(null);
    try {
      const repoName = name || (url ? url.split("/").slice(-1)[0].replace(/\.git$/, "") : "");
      await api.createRepo(repoName, tab === "github" ? url : null);
      setName(""); setUrl("");
      load();
    } catch (err) {
      setFormErr(err.message || "Failed to create repository");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorNote error={error} />;

  return (
    <div>
      <PageHeader subtitle="Code" title="Repositories" />
      <div className="row">
        <div className="col-lg-7">
          <Card title="Your repositories">
            {!repos ? <Loading /> : repos.length === 0 ? (
              <Empty icon="folder_open">No repositories yet. Import one from GitHub on the right →</Empty>
            ) : (
              <div>
                {repos.map((r) => (
                  <div className="repo-item" key={r.id}>
                    <i className="material-icons rico">{r.source_kind === "github" ? "cloud_download" : "book"}</i>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Link className="r-name" to={`/repos/${r.id}`}>{r.name}</Link>
                      <div className="r-meta">
                        <span className="badge badge-light">{r.source_kind}</span>
                        <span><span className="lang-dot" />{r.sol_files} Solidity</span>
                        <span>{r.files} file(s)</span>
                        {r.has_readme && <span><i className="material-icons align-middle" style={{ fontSize: 14 }}>menu_book</i> README</span>}
                      </div>
                    </div>
                    <Link className="btn btn-white btn-sm" to={`/repos/${r.id}`}>
                      <i className="material-icons align-middle" style={{ fontSize: 16 }}>code</i> Open
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
        <div className="col-lg-5">
          <Card title="Import a repository">
            <ul className="nav nav-pills mb-3">
              <li className="nav-item"><button className={`nav-link ${tab === "github" ? "active" : ""}`} onClick={() => setTab("github")} style={{ border: "none" }}>From GitHub</button></li>
              <li className="nav-item"><button className={`nav-link ${tab === "empty" ? "active" : ""}`} onClick={() => setTab("empty")} style={{ border: "none" }}>Empty repo</button></li>
            </ul>
            {tab === "github" && (
              <>
                <label className="text-muted" style={{ fontSize: 13 }}>GitHub URL</label>
                <input className="form-control mb-2" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repo" />
                <p className="repo-url">Public repos only. Sentinel shallow-clones it and pulls in every <code>.sol</code> file and the README.</p>
              </>
            )}
            <label className="text-muted" style={{ fontSize: 13 }}>Name {tab === "github" && "(optional)"}</label>
            <input className="form-control mb-3" value={name} onChange={(e) => setName(e.target.value)} placeholder="my-protocol" />
            <button className="btn btn-primary" onClick={create} disabled={busy || (tab === "github" && !url) || (tab === "empty" && !name)}>
              {busy ? <><span className="spin" /> &nbsp;Importing…</> : <><i className="material-icons align-middle" style={{ fontSize: 18 }}>add</i> {tab === "github" ? "Import from GitHub" : "Create repo"}</>}
            </button>
            {formErr && <div className="callout callout-bad mt-3">{formErr}</div>}
          </Card>
        </div>
      </div>
    </div>
  );
}
