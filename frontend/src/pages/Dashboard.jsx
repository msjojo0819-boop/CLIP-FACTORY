import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

const STATUS_COLORS = {
  queued: "bg-white/20",
  transcribing: "bg-yellow-500/70",
  scoring: "bg-yellow-500/70",
  cutting: "bg-blue-500/70",
  done: "bg-green-600/80",
  failed: "bg-red-600/80",
};

export default function Dashboard() {
  const { workspaceId } = useWorkspace();
  const [jobs, setJobs] = useState([]);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    api.listJobs().then(setJobs).catch((e) => setError(e.message));
    api.getUsageReport(workspaceId).then(setUsage).catch(() => {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [workspaceId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <Link to="/upload" className="btn btn-primary">+ New Upload</Link>
      </div>

      {error && <div className="card text-red-400 text-sm">{error} — is the backend running?</div>}

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Videos processed" value={usage?.videos_processed ?? "–"} />
        <Stat label="Clips generated" value={usage?.clips_generated ?? "–"} />
        <Stat label="Clips published" value={usage?.clips_published ?? "–"} />
        <Stat label="Minutes used this period" value={usage?.current_usage ? usage.current_usage.minutes_processed.toFixed(1) : "–"} />
      </div>

      <div className="card">
        <h2 className="text-white font-medium mb-3">Recent uploads / processing queue</h2>
        {jobs.length === 0 && <div className="text-white/40 text-sm">No videos yet. Upload one to get started.</div>}
        <div className="divide-y divide-white/10">
          {jobs.map((j) => (
            <Link
              key={j.job_id}
              to={j.status === "done" ? `/jobs/${j.job_id}/review` : `/jobs/${j.job_id}`}
              className="flex items-center justify-between py-3 hover:bg-white/5 px-2 -mx-2 rounded"
            >
              <div>
                <div className="text-white text-sm">{j.filename || j.job_id}</div>
                <div className="text-white/40 text-xs">{j.stage_detail}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-white/50 text-xs">{j.clip_count} clips</span>
                {j.warning_count > 0 && (
                  <span className="text-xs px-2 py-1 rounded-full text-amber-950 bg-amber-400/90" title={`${j.warning_count} warning(s) — open the review grid for details`}>
                    ⚠ {j.warning_count}
                  </span>
                )}
                <span className={`text-xs px-2 py-1 rounded-full text-white ${STATUS_COLORS[j.status] || "bg-white/20"}`}>
                  {j.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="card">
      <div className="text-white/40 text-xs mb-1">{label}</div>
      <div className="text-white text-2xl font-semibold">{value}</div>
    </div>
  );
}
