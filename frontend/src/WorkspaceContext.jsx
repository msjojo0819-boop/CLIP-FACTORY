import { createContext, useContext, useState } from "react";

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const [workspaceId, setWorkspaceId] = useState(
    () => localStorage.getItem("cf_workspace_id") || "default"
  );
  const changeWorkspace = (id) => {
    localStorage.setItem("cf_workspace_id", id);
    setWorkspaceId(id);
  };
  return (
    <WorkspaceContext.Provider value={{ workspaceId, setWorkspaceId: changeWorkspace }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
