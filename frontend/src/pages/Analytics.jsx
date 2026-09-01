import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

export default function Analytics() {
  const { workspaceId } = useWorkspace();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = () => api.getAnalytics(workspaceId).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [workspaceId]);

  const refresh = async () => {
    setBusy(true);
    setError(null);
    try {
      const d = await api.refreshAnalytics(workspaceId);
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Analytics</h1>
        <button onClick={refresh} disabled={busy} className="btn btn-primary">
          {busy ? "Pulling metrics..." : "Refresh from platforms"}
        </button>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}

      {data && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="card">
              <div className="text-white/40 text-xs mb-1">Best clip this week</div>
              <div className="text-white text-lg font-medium">
                {data.best_clip_this_week ? `${data.best_clip_this_week.engagement} engagement` : "No published data yet"}
              </div>
              {data.best_clip_this_week && (
                <div className="text-white/40 text-xs mt-1">{data.best_clip_this_week.platform} · {data.best_clip_this_week.title}</div>
              )}
            </div>
            <div className="card">
              <div className="text-white/40 text-xs mb-1">Best caption style</div>
              <div className="text-white text-lg font-medium">{data.best_caption_style || "—"}</div>
            </div>
            <div className="card">
              <div className="text-white/40 text-xs mb-1">Best clip length</div>
              <div className="text-white text-lg font-medium">{data.best_clip_length || "—"}</div>
            </div>
          </div>

          {data.scoring_weights && (
            <div className="card">
              <div className="text-white font-medium mb-2">Personalized moment-scoring weights</div>
              <div className="text-white/40 text-xs mb-3">
                Adjusts automatically as more of your clips get published and pull in real performance data.
              </div>
              {Object.entries(data.scoring_weights).map(([k, v]) => (
                <div key={k} className="flex items-center gap-3 mb-2">
                  <div className="text-white/70 text-sm w-48">{k}</div>
                  <div className="flex-1 bg-white/10 rounded-full h-2">
                    <div className="bg-brand-500 h-2 rounded-full" style={{ width: `${Math.min(100, (v / 2) * 100)}%` }} />
                  </div>
                  <div className="text-white/50 text-xs w-10 text-right">{v.toFixed(2)}</div>
                </div>
              ))}
            </div>
          )}

          <div className="text-white/40 text-xs">Sample size: {data.sample_size} published clips</div>
        </>
      )}
    </div>
  );
}
