import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

const CAPTION_STYLES = ["bold_pop", "minimal_clean", "neon_gaming", "podcast_classic"];

export default function Upload() {
  const { workspaceId } = useWorkspace();
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [minClips, setMinClips] = useState(5);
  const [maxClips, setMaxClips] = useState(15);
  const [minLen, setMinLen] = useState(15);
  const [maxLen, setMaxLen] = useState(180);
  const [sensitivity, setSensitivity] = useState(0.5);
  const [aspects, setAspects] = useState(["16:9", "9:16", "1:1"]);
  const [captionStyle, setCaptionStyle] = useState("bold_pop");
  const [addEmoji, setAddEmoji] = useState(true);
  const [censor, setCensor] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const toggleAspect = (a) =>
    setAspects((prev) => (prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]));

  const submit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Choose a video file first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.createJob(file, {
        workspaceId,
        minClips, maxClips,
        minClipSeconds: minLen, maxClipSeconds: maxLen,
        sensitivity,
        aspectRatios: aspects.join(","),
        captionStyle,
        addEmoji, censor,
      });
      navigate(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">New Upload</h1>

      <form onSubmit={submit} className="card space-y-5">
        <div>
          <label className="label">Video file (MP4, MOV, MKV — up to 4 hours / 20GB)</label>
          <input
            type="file"
            accept=".mp4,.mov,.mkv,video/*"
            onChange={(e) => setFile(e.target.files[0])}
            className="input"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Min clips</label>
            <input type="number" className="input" value={minClips} min={1} max={30}
                   onChange={(e) => setMinClips(+e.target.value)} />
          </div>
          <div>
            <label className="label">Max clips</label>
            <input type="number" className="input" value={maxClips} min={1} max={30}
                   onChange={(e) => setMaxClips(+e.target.value)} />
          </div>
          <div>
            <label className="label">Min clip length (sec)</label>
            <input type="number" className="input" value={minLen} min={5}
                   onChange={(e) => setMinLen(+e.target.value)} />
          </div>
          <div>
            <label className="label">Max clip length (sec)</label>
            <input type="number" className="input" value={maxLen} min={5}
                   onChange={(e) => setMaxLen(+e.target.value)} />
          </div>
        </div>

        <div>
          <label className="label">Sensitivity: fewer, higher-quality clips ← → more clips ({sensitivity})</label>
          <input type="range" min={0} max={1} step={0.05} value={sensitivity}
                 onChange={(e) => setSensitivity(+e.target.value)} className="w-full" />
        </div>

        <div>
          <label className="label">Aspect ratios to render</label>
          <div className="flex gap-2">
            {["16:9", "9:16", "1:1"].map((a) => (
              <button type="button" key={a} onClick={() => toggleAspect(a)}
                      className={`btn ${aspects.includes(a) ? "btn-primary" : "btn-secondary"}`}>
                {a}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">Caption style</label>
          <select className="input" value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value)}>
            {CAPTION_STYLES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>

        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm text-white/80">
            <input type="checkbox" checked={addEmoji} onChange={(e) => setAddEmoji(e.target.checked)} />
            Auto-emoji
          </label>
          <label className="flex items-center gap-2 text-sm text-white/80">
            <input type="checkbox" checked={censor} onChange={(e) => setCensor(e.target.checked)} />
            Profanity censor (bleep + blur)
          </label>
        </div>

        {error && <div className="text-red-400 text-sm">{error}</div>}

        <button type="submit" disabled={submitting} className="btn btn-primary w-full">
          {submitting ? "Uploading..." : "Process Video"}
        </button>
      </form>
    </div>
  );
}
