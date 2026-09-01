import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";

const STAGES = ["queued", "transcribing", "scoring", "cutting", "done"];

export default function Processing() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let stop = false;
    const poll = async () => {
      try {
        const j = await api.getJob(jobId);
        if (stop) return;
        setJob(j);
        if (j.status === "done") {
          navigate(`/jobs/${jobId}/review`);
          return;
        }
        if (j.status !== "failed") setTimeout(poll, 2500);
      } catch (e) {
        if (!stop) setError(e.message);
      }
    };
    poll();
    return () => { stop = true; };
  }, [jobId, navigate]);

  const currentIdx = job ? STAGES.indexOf(job.status) : 0;

  return (
    <div className="max-w-xl mx-auto mt-16 text-center space-y-6">
      <h1 className="text-2xl font-semibold text-white">Processing your video</h1>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      {job && (
        <>
          <div className="flex justify-center gap-2">
            {STAGES.map((s, i) => (
              <div key={s}
                   className={`h-2 flex-1 rounded-full ${i <= currentIdx ? "bg-brand-500" : "bg-white/10"}`} />
            ))}
          </div>
          <div className="text-white/70 text-lg">{job.stage_detail}</div>
          {job.status === "failed" && (
            <div className="card text-red-400 text-sm text-left">
              <div className="font-medium mb-1">Something went wrong:</div>
              {job.error}
            </div>
          )}
        </>
      )}
    </div>
  );
}
