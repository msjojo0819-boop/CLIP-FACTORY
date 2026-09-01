import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

const CAPTION_STYLES = ["bold_pop", "minimal_clean", "neon_gaming", "podcast_classic"];
const PLATFORMS = ["tiktok", "instagram", "youtube"];

export default function Settings() {
  const { workspaceId } = useWorkspace();
  const [ws, setWs] = useState(null);
  const [name, setName] = useState("");
  const [style, setStyle] = useState("bold_pop");
  const [logoFile, setLogoFile] = useState(null);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("editor");
  const [message, setMessage] = useState(null);

  const load = () => api.getWorkspace(workspaceId).then((w) => {
    setWs(w);
    setName(w.name);
    setStyle(w.default_caption_style);
  });
  useEffect(() => { load(); }, [workspaceId]);

  const saveGeneral = async () => {
    await api.updateWorkspace(workspaceId, { name, default_caption_style: style });
    setMessage("Saved.");
    load();
  };

  const uploadLogo = async () => {
    if (!logoFile) return;
    await api.uploadLogo(workspaceId, logoFile);
    setMessage("Logo uploaded — applied to future clips.");
    load();
  };

  const addMember = async () => {
    if (!userId) return;
    await api.addTeamMember(workspaceId, userId, role);
    setUserId("");
    load();
  };

  const removeMember = async (id) => {
    await api.removeTeamMember(workspaceId, id);
    load();
  };

  if (!ws) return <div className="text-white/50">Loading…</div>;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Brand & Workspace Settings</h1>

      <div className="card space-y-4">
        <div className="text-white font-medium">General</div>
        <div>
          <label className="label">Brand name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Default caption style</label>
          <select className="input" value={style} onChange={(e) => setStyle(e.target.value)}>
            {CAPTION_STYLES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>
        <button onClick={saveGeneral} className="btn btn-primary">Save</button>
      </div>

      <div className="card space-y-3">
        <div className="text-white font-medium">Logo / watermark</div>
        {ws.logo_path && <div className="text-white/40 text-xs">Current: {ws.logo_path.split("/").pop()}</div>}
        <input type="file" accept="image/*" onChange={(e) => setLogoFile(e.target.files[0])} className="input" />
        <button onClick={uploadLogo} className="btn btn-secondary">Upload logo</button>
      </div>

      <div className="card space-y-3">
        <div className="text-white font-medium">Connected accounts</div>
        {PLATFORMS.map((p) => {
          const connected = ws.connected_accounts?.[p];
          return (
            <div key={p} className="flex items-center justify-between">
              <span className="text-white/70 text-sm capitalize">{p}</span>
              {connected ? (
                <span className="text-green-400 text-xs">Connected</span>
              ) : (
                <a href={api.connectAuthorizeUrl(workspaceId, p)} className="btn btn-secondary text-xs">Connect</a>
              )}
            </div>
          );
        })}
      </div>

      <div className="card space-y-3">
        <div className="text-white font-medium">Team members</div>
        <div className="divide-y divide-white/10">
          {(ws.team_members || []).map((m) => (
            <div key={m.user_id} className="flex items-center justify-between py-2">
              <span className="text-white/70 text-sm">{m.user_id} — {m.role}</span>
              <button onClick={() => removeMember(m.user_id)} className="btn btn-danger text-xs">Remove</button>
            </div>
          ))}
          {(!ws.team_members || ws.team_members.length === 0) && (
            <div className="text-white/40 text-sm py-2">No team members yet — you have full solo access.</div>
          )}
        </div>
        <div className="flex gap-2">
          <input className="input" placeholder="user id / email" value={userId} onChange={(e) => setUserId(e.target.value)} />
          <select className="input w-40" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="editor">editor</option>
            <option value="admin">admin</option>
          </select>
          <button onClick={addMember} className="btn btn-primary">Add</button>
        </div>
      </div>

      {message && <div className="text-white/50 text-sm">{message}</div>}
    </div>
  );
}
