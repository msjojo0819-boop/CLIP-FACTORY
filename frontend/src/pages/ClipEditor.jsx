import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

const CAPTION_STYLES = ["bold_pop", "minimal_clean", "neon_gaming", "podcast_classic"];
const PLATFORMS = ["tiktok", "instagram", "youtube"];

export default function ClipEditor() {
  const { jobId, clipId } = useParams();
  const { workspaceId } = useWorkspace();
  const [clip, setClip] = useState(null);
  const [aspect, setAspect] = useState("9:16");
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [captionStyle, setCaptionStyle] = useState("bold_pop");
  const [logo, setLogo] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [platform, setPlatform] = useState("tiktok");

  const load = async () => {
    const clips = await api.getClips(jobId);
    const c = clips.find((x) => x.id === clipId);
    setClip(c);
    if (c) {
      setStart(c.start);
      setEnd(c.end);
      setCaptionStyle(c.caption_style || "bold_pop");
      setLogo(c.logo_applied);
      setAspect(c.aspect_ratios?.[0] || "9:16");
    }
  };
  useEffect(() => { load(); }, [jobId, clipId]);

  const recut = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.recutClip(jobId, clipId, { start, end, caption_style: captionStyle, logo });
      await load();
      setMessage("Re-cut complete.");
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  const publish = async (scheduledTime) => {
    setBusy(true);
    setMessage(null);
    try {
      const res = await api.publishClip(jobId, clipId, {
        platform, workspace_id: workspaceId, aspect,
        title: clip.title_suggestions?.[0], scheduled_time: scheduledTime,
      });
      setMessage(scheduledTime ? `Scheduled for ${scheduledTime}.` : `Publish queued (status: ${res.status}).`);
    } catch (e) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!clip) return <div className="text-white/50">Loading clip…</div>;

  return (
    <div className="max-w-3xl space-y-6">
      <Link to={`/jobs/${jobId}/review`} className="text-white/50 text-sm hover:text-white">← Back to review</Link>
      <h1 className="text-2xl font-semibold text-white">Edit Clip</h1>

      <div className="grid grid-cols-2 gap-6">
        <div className="card">
          <div className="flex gap-2 mb-2">
            {(clip.aspect_ratios || []).map((a) => (
              <button key={a} onClick={() => setAspect(a)}
                      className={`btn ${aspect === a ? "btn-primary" : "btn-secondary"}`}>{a}</button>
            ))}
          </div>
          <video
            key={api.clipDownloadUrl(jobId, clipId, aspect)}
            controls
            className="w-full rounded-lg bg-black"
            src={api.clipDownloadUrl(jobId, clipId, aspect)}
          />
        </div>

        <div className="space-y-4">
          <div className="card space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Trim start (sec)</label>
                <input type="number" step="0.1" className="input" value={start} onChange={(e) => setStart(+e.target.value)} />
              </div>
              <div>
                <label className="label">Trim end (sec)</label>
                <input type="number" step="0.1" className="input" value={end} onChange={(e) => setEnd(+e.target.value)} />
              </div>
            </div>
            <div>
              <label className="label">Caption style</label>
              <select className="input" value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value)}>
                {CAPTION_STYLES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-white/80">
              <input type="checkbox" checked={logo} onChange={(e) => setLogo(e.target.checked)} />
              Apply brand logo/watermark
            </label>
            <button onClick={recut} disabled={busy} className="btn btn-primary w-full">
              {busy ? "Re-rendering..." : "Re-cut with these settings"}
            </button>
          </div>

          <div className="card space-y-3">
            <div className="text-white font-medium text-sm">Titles</div>
            {(clip.title_suggestions || []).map((t, i) => (
              <div key={i} className="text-white/70 text-sm">• {t}</div>
            ))}
            <div className="text-white font-medium text-sm pt-2">Hashtags</div>
            <div className="text-white/50 text-xs">{(clip.hashtags || []).join(" ")}</div>
          </div>

          <div className="card space-y-3">
            <div className="text-white font-medium text-sm">Publish</div>
            <select className="input" value={platform} onChange={(e) => setPlatform(e.target.value)}>
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <div className="flex gap-2">
              <button onClick={() => publish(null)} disabled={busy} className="btn btn-primary flex-1">Publish Now</button>
            </div>
            <a href={api.connectAuthorizeUrl(workspaceId, platform)} className="text-brand-400 text-xs underline">
              Connect {platform} account
            </a>
          </div>

          {message && <div className="text-sm text-white/70">{message}</div>}
        </div>
      </div>
    </div>
  );
}
