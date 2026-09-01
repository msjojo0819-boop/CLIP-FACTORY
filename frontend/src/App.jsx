import { NavLink, Route, Routes } from "react-router-dom";
import { WorkspaceProvider, useWorkspace } from "./WorkspaceContext.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Upload from "./pages/Upload.jsx";
import Processing from "./pages/Processing.jsx";
import ReviewGrid from "./pages/ReviewGrid.jsx";
import ClipEditor from "./pages/ClipEditor.jsx";
import Export from "./pages/Export.jsx";
import Calendar from "./pages/Calendar.jsx";
import Analytics from "./pages/Analytics.jsx";
import Settings from "./pages/Settings.jsx";
import Billing from "./pages/Billing.jsx";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/upload", label: "New Upload" },
  { to: "/calendar", label: "Content Calendar" },
  { to: "/analytics", label: "Analytics" },
  { to: "/settings", label: "Brand & Workspace" },
  { to: "/billing", label: "Billing" },
];

function WorkspaceSwitcher() {
  const { workspaceId, setWorkspaceId } = useWorkspace();
  return (
    <div className="px-4 py-3 border-b border-white/10">
      <label className="label">Workspace</label>
      <input
        className="input"
        value={workspaceId}
        onChange={(e) => setWorkspaceId(e.target.value || "default")}
        placeholder="workspace id"
      />
    </div>
  );
}

function App() {
  return (
    <WorkspaceProvider>
      <div className="min-h-screen flex">
        <aside className="w-64 shrink-0 bg-[#131318] border-r border-white/10 flex flex-col">
          <div className="px-4 py-4 border-b border-white/10">
            <div className="text-xl font-bold text-white">🎬 Clip Factory</div>
            <div className="text-xs text-white/40">Finished-product build</div>
          </div>
          <WorkspaceSwitcher />
          <nav className="flex-1 p-2 space-y-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-lg text-sm ${
                    isActive ? "bg-brand-600 text-white" : "text-white/70 hover:bg-white/5"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1 p-6 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/jobs/:jobId" element={<Processing />} />
            <Route path="/jobs/:jobId/review" element={<ReviewGrid />} />
            <Route path="/jobs/:jobId/clips/:clipId" element={<ClipEditor />} />
            <Route path="/jobs/:jobId/export" element={<Export />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/billing" element={<Billing />} />
          </Routes>
        </main>
      </div>
    </WorkspaceProvider>
  );
}

export default App;
