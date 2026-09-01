import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";

export default function ReviewGrid() {
  const { jobId } = useParams();
  const [clips, setClips] = useState([]);
  const [error, setError] = useState(null);

  const load = () => api.getClips(jobId).then(setClips).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [jobId]);

  const toggleKeep = async (clip) => {
    const next = clip.status === "finalized" ? "draft" : "finalized";
    await api.setClipStatus(jobId, clip.id, next);
    load();
  };

  const keptCount = clips.filter((c) => c.status === "finalized").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Clip Review</h1>
        <Link to={`/jobs/${jobId}/export`} className="btn btn-primary">
          Continue to Export ({keptCount || clips.length} clip{(keptCount || clips.length) === 1 ? "" : "s"})
        </Link>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="grid grid-cols-3 gap-4">
        {clips.map((clip) => (
          <div key={clip.id} className="card space-y-3">
            <div className="aspect-[9/16] bg-black rounded-lg overflow-hidden flex items-center justify-center">
              {clip.thumbnail_path ? (
                <img src={api.thumbnailUrl(jobId, clip.id)} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="text-white/30 text-xs">No preview</span>
              )}
            </div>
            <div>
              <div className="text-white text-sm font-medium truncate">
                {clip.title_suggestions?.[0] || "Untitled clip"}
              </div>
              <div className="text-white/40 text-xs">
                {(clip.end - clip.start).toFixed(1)}s · score {clip.score.toFixed(1)} · {clip.reason}
              </div>
              {clip.warnings?.length > 0 && (
                <div className="mt-1 text-amber-400 text-xs flex items-start gap-1" title={clip.warnings.join("\n")}>
                  <span>⚠</span>
                  <span>{clip.warnings.length === 1 ? clip.warnings[0] : `${clip.warnings.length} issues — hover to see`}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Link to={`/jobs/${jobId}/clips/${clip.id}`} className="btn btn-secondary flex-1 text-center">
                Edit
              </Link>
              <button
                onClick={() => toggleKeep(clip)}
                className={`btn flex-1 ${clip.status === "finalized" ? "btn-primary" : "btn-secondary"}`}
              >
                {clip.status === "finalized" ? "✓ Kept" : "Keep"}
              </button>
            </div>
          </div>
        ))}
      </div>

      {clips.length === 0 && !error && (
        <div className="text-white/40 text-sm">No clips found for this job.</div>
      )}
    </div>
  );
}
