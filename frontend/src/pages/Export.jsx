import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api.js";

export default function Export() {
  const { jobId } = useParams();
  const [clips, setClips] = useState([]);

  useEffect(() => { api.getClips(jobId).then(setClips); }, [jobId]);

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Export / Publish</h1>

      <div className="card flex items-center justify-between">
        <div>
          <div className="text-white font-medium">Download everything</div>
          <div className="text-white/40 text-sm">All aspect ratios + thumbnails as one ZIP</div>
        </div>
        <a href={api.jobZipUrl(jobId)} className="btn btn-primary">Download ZIP</a>
      </div>

      <div className="card">
        <div className="text-white font-medium mb-3">Individual clips</div>
        <div className="divide-y divide-white/10">
          {clips.map((c) => (
            <div key={c.id} className="flex items-center justify-between py-3">
              <div className="text-white text-sm">{c.title_suggestions?.[0] || c.id}</div>
              <div className="flex gap-2">
                {(c.aspect_ratios || []).map((a) => (
                  <a key={a} href={api.clipDownloadUrl(jobId, c.id, a)} className="btn btn-secondary text-xs">
                    {a}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="text-white/40 text-sm">
        Want to schedule these instead? Open a clip's editor and use the Publish panel, or check the Content Calendar.
      </div>
    </div>
  );
}
