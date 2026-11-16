import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, session } from "../api.js";
import { Card, ErrorNote, Loading } from "../components/ui.jsx";

const CAN_WRITE = ["analyst", "admin"];

// Turn a flat list of "src/token/Vault.sol" paths into what lives directly under `dir`.
function entriesAt(paths, dir) {
  const prefix = dir ? dir + "/" : "";
  const folders = new Set();
  const files = [];
  for (const p of paths) {
    if (!p.startsWith(prefix)) continue;
    const rest = p.slice(prefix.length);
    if (!rest) continue;
    const slash = rest.indexOf("/");
    if (slash === -1) files.push({ name: rest, path: p });
    else folders.add(rest.slice(0, slash));
  }
  return {
    folders: [...folders].sort().map((name) => ({ name, path: prefix + name })),
    files: files.sort((a, b) => a.name.localeCompare(b.name)),
  };
}

function copy(text, e) {
  navigator.clipboard?.writeText(text);
  if (e) { const t = e.target; const old = t.textContent; t.textContent = "Copied!"; setTimeout(() => (t.textContent = old), 1200); }
}

export default function RepoDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const canWrite = CAN_WRITE.includes(session().role);

  const [repo, setRepo] = useState(null);
  const [error, setError] = useState(null);
  const [dir, setDir] = useState("");          // current folder ("" = root)
  const [blob, setBlob] = useState(null);      // selected file path (null = browsing)
  const [content, setContent] = useState(null);
  const [showCode, setShowCode] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ path: "", content: "" });
  const [busy, setBusy] = useState(false);

  function load() { api.getRepo(id).then(setRepo).catch(setError); }
  useEffect(load, [id]);

  const here = useMemo(() => entriesAt(repo?.tree || [], dir), [repo, dir]);

  function openFile(path) {
    setBlob(path); setContent(null);
    api.getRepoFile(id, path).then((r) => setContent(r.content)).catch(setError);
  }

  async function analyze() {
    setBusy(true);
    try { const scan = await api.analyzeRepoFile(id, blob); nav(`/scans/${scan.id}`); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }

  async function saveFile() {
    if (!form.path) return;
    setBusy(true);
    try {
      await api.addRepoFile(id, form.path.trim(), form.content);
      setShowAdd(false); setForm({ path: "", content: "" });
      load();
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  if (error) return <ErrorNote error={error} />;
  if (!repo) return <Loading />;

  const isEmpty = (repo.tree || []).length === 0;
  const solCount = (repo.sol_paths || []).length;
  const cloneUrl = repo.github_url
    ? repo.github_url.replace(/\/?$/, "").replace(/(\.git)?$/, ".git")
    : `https://github.com/your-org/${repo.name}.git`;

  return (
    <div>
      {/* ---- repo header (GitHub breadcrumb) ---- */}
      <div className="repo-crumb">
        <i className="material-icons align-middle" style={{ fontSize: 22, color: "#9aa5b5" }}>book</i>{" "}
        <span>{session().org?.slice(0, 8) || "org"}</span>
        <span className="sep">/</span>
        <b>{repo.name}</b>
      </div>
      <div className="repo-sub">
        <span className="badge badge-light">{repo.source_kind}</span>
        <span><b>{repo.tree.length}</b> file(s)</span>
        <span><span className="lang-dot" />{solCount} Solidity</span>
        {repo.github_url && (
          <a className="repo-url" href={repo.github_url} target="_blank" rel="noreferrer">
            <i className="material-icons align-middle" style={{ fontSize: 14 }}>link</i> {repo.github_url}
          </a>
        )}
      </div>

      <div className="repo-toolbar">
        <span className="branch-chip"><i className="material-icons">account_tree</i> main</span>
        <div className="repo-actions">
          {canWrite && (
            <button className="btn btn-white btn-sm" onClick={() => { setShowAdd((v) => !v); setBlob(null); }}>
              <i className="material-icons align-middle" style={{ fontSize: 16 }}>note_add</i> Add file
            </button>
          )}
          <div className="code-dd">
            <button className="btn btn-primary btn-sm" onClick={() => setShowCode((v) => !v)}>
              <i className="material-icons align-middle" style={{ fontSize: 16 }}>code</i> Code <i className="material-icons align-middle" style={{ fontSize: 16 }}>arrow_drop_down</i>
            </button>
            {showCode && (
              <div className="code-panel" onMouseLeave={() => setShowCode(false)}>
                <h6>Clone</h6>
                <div className="clone-row">
                  <input className="clone-input" readOnly value={cloneUrl} onFocus={(e) => e.target.select()} />
                  <button className="btn btn-white btn-sm" onClick={(e) => copy(cloneUrl, e)}>
                    <i className="material-icons align-middle" style={{ fontSize: 16 }}>content_copy</i>
                  </button>
                </div>
                {repo.github_url ? (
                  <p className="repo-url mt-2 mb-0">This mirrors a public GitHub repository.</p>
                ) : (
                  <p className="repo-url mt-2 mb-0">Sentinel isn't a git host — this URL is a placeholder. Use <b>Add file</b> to put code in, or import an existing GitHub repo.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ---- add-file form ---- */}
      {showAdd && (
        <div className="addfile">
          <div className="row">
            <div className="col-12 mb-2">
              <label className="text-muted" style={{ fontSize: 13 }}>File path (e.g. <code>src/Vault.sol</code> or <code>README.md</code>)</label>
              <input className="form-control" value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} placeholder="src/MyContract.sol" />
            </div>
            <div className="col-12">
              <label className="text-muted" style={{ fontSize: 13 }}>Contents</label>
              <textarea className="form-control mono" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="// paste the file contents here" />
            </div>
          </div>
          <div className="mt-3">
            <button className="btn btn-primary btn-sm" onClick={saveFile} disabled={busy || !form.path}>
              {busy ? <><span className="spin" /> &nbsp;Committing…</> : <><i className="material-icons align-middle" style={{ fontSize: 16 }}>check</i> Commit file</>}
            </button>
            <button className="btn btn-white btn-sm ml-2" onClick={() => setShowAdd(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* ---- body: blob view, empty quick-setup, or file list ---- */}
      {blob ? (
        <BlobView repo={repo} path={blob} content={content} canWrite={canWrite} busy={busy}
          onBack={() => setBlob(null)} onAnalyze={analyze} />
      ) : isEmpty && !showAdd ? (
        <QuickSetup repo={repo} cloneUrl={cloneUrl} canWrite={canWrite}
          onCreate={() => { setShowAdd(true); setForm({ path: "README.md", content: `# ${repo.name}\n` }); }} />
      ) : (
        <>
          <FileList here={here} dir={dir} onDir={setDir} onFile={openFile} />
          {dir === "" && repo.readme && <Readme text={repo.readme} />}
        </>
      )}
    </div>
  );
}

function FileList({ here, dir, onDir, onFile }) {
  const parts = dir ? dir.split("/") : [];
  return (
    <>
      {dir && (
        <div className="repo-sub" style={{ marginTop: 4 }}>
          <span style={{ cursor: "pointer", color: "var(--s-primary)" }} onClick={() => onDir("")}>root</span>
          {parts.map((seg, i) => (
            <span key={i}>
              <span className="sep">/</span>
              <span style={{ cursor: "pointer", color: i === parts.length - 1 ? "var(--s-ink)" : "var(--s-primary)" }}
                onClick={() => onDir(parts.slice(0, i + 1).join("/"))}>{seg}</span>
            </span>
          ))}
        </div>
      )}
      <div className="gh-files">
        {dir && (
          <button className="gh-row folder" onClick={() => onDir(parts.slice(0, -1).join("/"))}>
            <i className="material-icons">turn_left</i><span className="gh-name gh-up">..</span>
          </button>
        )}
        {here.folders.map((f) => (
          <button key={f.path} className="gh-row folder" onClick={() => onDir(f.path)}>
            <i className="material-icons">folder</i><span className="gh-name">{f.name}</span>
          </button>
        ))}
        {here.files.map((f) => {
          const sol = f.name.endsWith(".sol");
          return (
            <button key={f.path} className={`gh-row file ${sol ? "sol" : ""}`} onClick={() => onFile(f.path)}>
              <i className="material-icons">{sol ? "description" : "insert_drive_file"}</i>
              <span className="gh-name">{f.name}</span>
              {sol && <span className="gh-meta">Solidity · click to view</span>}
            </button>
          );
        })}
      </div>
    </>
  );
}

function BlobView({ repo, path, content, canWrite, busy, onBack, onAnalyze }) {
  const isSol = path.endsWith(".sol");
  const lines = content == null ? [] : content.split("\n");
  return (
    <>
      <div className="repo-sub" style={{ marginTop: 4 }}>
        <span style={{ cursor: "pointer", color: "var(--s-primary)" }} onClick={onBack}>{repo.name}</span>
        <span className="sep">/</span><span className="mono">{path}</span>
      </div>
      <div className="blob-head">
        <div>
          <span className="blob-path"><i className="material-icons align-middle" style={{ fontSize: 16, color: "#9aa5b5" }}>{isSol ? "description" : "insert_drive_file"}</i> <span className="mono">{path}</span></span>
          {content != null && <span className="blob-meta ml-3">{lines.length} lines · {content.length} chars</span>}
        </div>
        <div>
          <button className="btn btn-white btn-sm" onClick={onBack}>
            <i className="material-icons align-middle" style={{ fontSize: 16 }}>arrow_back</i> Files
          </button>
          {isSol && canWrite && (
            <button className="btn btn-primary btn-sm ml-2" onClick={onAnalyze} disabled={busy}>
              {busy ? <><span className="spin" /> &nbsp;Analyzing…</> : <><i className="material-icons align-middle" style={{ fontSize: 16 }}>play_arrow</i> Analyze this file</>}
            </button>
          )}
        </div>
      </div>
      <div className="blob-body">
        {content == null ? <div className="p-3"><Loading /></div> : (
          <table><tbody>
            {lines.map((line, i) => (
              <tr key={i}><td className="ln">{i + 1}</td><td className="src">{line || " "}</td></tr>
            ))}
          </tbody></table>
        )}
      </div>
      {isSol && (
        <p className="plain-note mt-3">
          Pressing <b>Analyze this file</b> compiles the whole repository (so imports resolve), runs static
          analysis and builds the attack graph for this contract.
        </p>
      )}
    </>
  );
}

function Readme({ text }) {
  return (
    <div className="gh-readme">
      <div className="gh-readme-head"><i className="material-icons">menu_book</i> README.md</div>
      <div className="gh-readme-body"><pre style={{ fontFamily: "var(--sf)" }}>{text}</pre></div>
    </div>
  );
}

function QuickSetup({ repo, cloneUrl, canWrite, onCreate }) {
  const c1 = `echo "# ${repo.name}" >> README.md\ngit init\ngit add README.md\ngit commit -m "first commit"\ngit branch -M main\ngit remote add origin ${cloneUrl}\ngit push -u origin main`;
  const c2 = `git remote add origin ${cloneUrl}\ngit branch -M main\ngit push -u origin main`;
  return (
    <Card title="Quick setup — get some code in here">
      <p className="plain-note mb-4">
        This repository is empty. Get started by <b>adding a file</b> in Sentinel, or import an existing
        GitHub repo from the Repositories page. The git commands below are the familiar GitHub setup, shown
        for reference — Sentinel stores files itself, it is not a live git remote.
      </p>

      <div className="quick-grid">
        <div className="quick-tile">
          <i className="material-icons">note_add</i>
          <h6>Create a new file</h6>
          <p>Add a <code>.sol</code> contract or a README directly in the browser.</p>
          <button className="btn btn-primary btn-sm" onClick={onCreate} disabled={!canWrite}>Create a file</button>
        </div>
        <div className="quick-tile">
          <i className="material-icons">cloud_download</i>
          <h6>Import from GitHub</h6>
          <p>Shallow-clone any public repo and pull in every Solidity file automatically.</p>
          <a className="btn btn-white btn-sm" href="/repos">Go to import</a>
        </div>
      </div>

      <h6 className="text-muted" style={{ fontSize: 13, marginTop: 6 }}>…or create a new repository on the command line</h6>
      <div className="cmd-block mb-4">
        <button className="copy" onClick={(e) => copy(c1, e)}>Copy</button>
        {c1.split("\n").map((l, i) => (
          <div key={i}>{l.startsWith("echo") || l.startsWith("git") ? l : <span className="cmt">{l}</span>}</div>
        ))}
      </div>

      <h6 className="text-muted" style={{ fontSize: 13 }}>…or push an existing repository from the command line</h6>
      <div className="cmd-block">
        <button className="copy" onClick={(e) => copy(c2, e)}>Copy</button>
        {c2.split("\n").map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </Card>
  );
}
