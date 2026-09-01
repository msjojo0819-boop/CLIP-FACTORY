// Thin fetch wrapper over the Clip Factory backend (see ../../README.md).
// Every screen in this app is real, wired to a real endpoint — nothing
// here is mocked data.
const BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

function form(fields) {
  const f = new FormData();
  Object.entries(fields).forEach(([k, v]) => {
    if (v !== undefined && v !== null) f.append(k, v);
  });
  return f;
}

export const api = {
  base: BASE,

  // Jobs / pipeline
  listJobs: () => req("/jobs"),
  getJob: (id) => req(`/jobs/${id}`),
  getClips: (jobId) => req(`/jobs/${jobId}/clips`),
  createJob: (file, opts) => {
    const f = form({
      file,
      workspace_id: opts.workspaceId || "default",
      min_clips: opts.minClips ?? 5,
      max_clips: opts.maxClips ?? 15,
      min_clip_seconds: opts.minClipSeconds ?? 15,
      max_clip_seconds: opts.maxClipSeconds ?? 180,
      sensitivity: opts.sensitivity ?? 0.5,
      aspect_ratios: opts.aspectRatios || "16:9,9:16,1:1",
      caption_style: opts.captionStyle || null,
      add_emoji: opts.addEmoji ?? true,
      censor: opts.censor ?? false,
    });
    return req("/jobs", { method: "POST", body: f });
  },
  clipDownloadUrl: (jobId, clipId, aspect) => `${BASE}/clips/${jobId}/${clipId}/download?aspect=${encodeURIComponent(aspect)}`,
  setClipStatus: (jobId, clipId, status) => req(`/jobs/${jobId}/clips/${clipId}/status`, { method: "PATCH", body: form({ status }) }),
  recutClip: (jobId, clipId, fields) => req(`/jobs/${jobId}/clips/${clipId}/recut`, { method: "POST", body: form(fields) }),
  thumbnailUrl: (jobId, clipId) => `${BASE}/clips/${jobId}/${clipId}/thumbnail`,
  jobZipUrl: (jobId) => `${BASE}/jobs/${jobId}/download`,

  // Workspace / brand settings
  getWorkspace: (id) => req(`/workspaces/${id}`),
  listWorkspaces: () => req("/workspaces"),
  updateWorkspace: (id, fields) => req(`/workspaces/${id}`, { method: "PUT", body: form(fields) }),
  uploadLogo: (id, file) => req(`/workspaces/${id}/logo`, { method: "POST", body: form({ file }) }),
  addTeamMember: (id, userId, role) => req(`/workspaces/${id}/team`, { method: "POST", body: form({ user_id: userId, role }) }),
  removeTeamMember: (id, userId) => req(`/workspaces/${id}/team/${userId}`, { method: "DELETE" }),

  // Publishing
  connectAuthorizeUrl: (workspaceId, platform) => `${BASE}/workspaces/${workspaceId}/connect/${platform}/authorize`,
  publishClip: (jobId, clipId, fields) => req(`/clips/${jobId}/${clipId}/publish`, { method: "POST", body: form(fields) }),
  getCalendar: (workspaceId) => req(`/workspaces/${workspaceId}/calendar`),
  cancelScheduledPost: (postId) => req(`/scheduled-posts/${postId}`, { method: "DELETE" }),

  // Analytics
  getAnalytics: (workspaceId) => req(`/workspaces/${workspaceId}/analytics`),
  refreshAnalytics: (workspaceId) => req(`/workspaces/${workspaceId}/analytics/refresh`, { method: "POST" }),
  getUsageReport: (workspaceId) => req(`/workspaces/${workspaceId}/usage-report`),

  // Billing
  listPlans: () => req("/billing/plans"),
  createCheckout: (workspaceId, planId, email) => req("/billing/checkout", { method: "POST", body: form({ workspace_id: workspaceId, plan_id: planId, email }) }),
  openBillingPortal: (workspaceId) => req("/billing/portal", { method: "POST", body: form({ workspace_id: workspaceId }) }),
};
