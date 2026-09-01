import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useWorkspace } from "../WorkspaceContext.jsx";

export default function Billing() {
  const { workspaceId } = useWorkspace();
  const [plans, setPlans] = useState(null);
  const [ws, setWs] = useState(null);
  const [usage, setUsage] = useState(null);
  const [message, setMessage] = useState(null);

  const load = () => {
    api.listPlans().then(setPlans);
    api.getWorkspace(workspaceId).then(setWs);
    api.getUsageReport(workspaceId).then(setUsage);
  };
  useEffect(() => { load(); }, [workspaceId]);

  const subscribe = async (planId) => {
    setMessage(null);
    try {
      const res = await api.createCheckout(workspaceId, planId);
      window.location.href = res.checkout_url;
    } catch (e) {
      setMessage(e.message);
    }
  };

  const openPortal = async () => {
    setMessage(null);
    try {
      const res = await api.openBillingPortal(workspaceId);
      window.location.href = res.portal_url;
    } catch (e) {
      setMessage(e.message);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold text-white">Billing & Account</h1>

      {ws && usage && (
        <div className="card flex items-center justify-between">
          <div>
            <div className="text-white font-medium capitalize">{ws.plan?.replace("_", " ")} plan</div>
            <div className="text-white/40 text-sm">
              {usage.current_usage.minutes_processed.toFixed(1)} min processed this period
            </div>
          </div>
          <button onClick={openPortal} className="btn btn-secondary">Manage subscription</button>
        </div>
      )}

      {message && <div className="text-red-400 text-sm">{message}</div>}

      <div className="grid grid-cols-2 gap-4">
        {plans && Object.values(plans).map((p) => (
          <div key={p.id} className="card space-y-2">
            <div className="text-white font-medium">{p.name}</div>
            <div className="text-white text-2xl">
              {p.price_usd === 0 ? "Free" : p.price_usd ? `$${p.price_usd}/mo` : "Custom"}
            </div>
            <ul className="text-white/50 text-xs space-y-1">
              {p.id === "free_trial" ? (
                <li>1 video, 3 clips (watermarked)</li>
              ) : (
                <li>{p.minutes_per_month ? `${p.minutes_per_month} min/mo` : "Unlimited minutes"}</li>
              )}
              <li>{p.max_workspaces ? `${p.max_workspaces} workspace(s)` : "Unlimited workspaces"}</li>
              {p.direct_publishing && <li>✓ Direct publishing</li>}
              {p.analytics && <li>✓ Analytics</li>}
              {p.team_seats && <li>✓ Team seats</li>}
              {p.priority_processing && <li>✓ Priority processing</li>}
            </ul>
            {p.id !== "free_trial" && (
              <button onClick={() => subscribe(p.id)} className="btn btn-primary w-full mt-2">
                {ws?.plan === p.id ? "Current plan" : "Subscribe"}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="text-white/40 text-xs">
        Overage past your plan's minutes bills automatically at ${plans ? "the configured per-minute rate" : "…"}.
      </div>
    </div>
  );
}
