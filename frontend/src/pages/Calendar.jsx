import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

const STATUS_COLORS = {
  scheduled: "bg-yellow-500/70",
  publishing: "bg-blue-500/70",
  published: "bg-green-600/80",
  failed: "bg-red-600/80",
};

export default function Calendar() {
  const { workspaceId } = useWorkspace();
  const [posts, setPosts] = useState([]);
  const [error, setError] = useState(null);

  const load = () => api.getCalendar(workspaceId).then(setPosts).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [workspaceId]);

  const cancel = async (id) => {
    await api.cancelScheduledPost(id);
    load();
  };

  const sorted = [...posts].sort((a, b) => new Date(a.scheduled_time) - new Date(b.scheduled_time));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Content Calendar</h1>
      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="card">
        {sorted.length === 0 && <div className="text-white/40 text-sm">Nothing scheduled yet.</div>}
        <div className="divide-y divide-white/10">
          {sorted.map((p) => (
            <div key={p.id} className="flex items-center justify-between py-3">
              <div>
                <div className="text-white text-sm">{p.title || p.clip_id}</div>
                <div className="text-white/40 text-xs">
                  {p.platform} · {new Date(p.scheduled_time).toLocaleString()}
                </div>
                {p.error && <div className="text-red-400 text-xs mt-1">{p.error}</div>}
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full text-white ${STATUS_COLORS[p.status] || "bg-white/20"}`}>
                  {p.status}
                </span>
                {p.status === "scheduled" && (
                  <button onClick={() => cancel(p.id)} className="btn btn-danger text-xs">Cancel</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
