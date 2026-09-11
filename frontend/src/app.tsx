import { Route, Routes } from "react-router-dom";

import { AppLayout } from "./layouts/app-layout";
import { DashboardPage } from "./pages/dashboard-page";
import { ProjectBoardPage } from "./pages/project-board-page";
import { ProjectSprintsPage } from "./pages/project-sprints-page";
import { ProjectWorkspacePage } from "./pages/project-workspace-page";
import { ProjectsPage } from "./pages/projects-page";
import { ReportsPage } from "./pages/reports-page";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectKey" element={<ProjectWorkspacePage />} />
        <Route path="projects/:projectKey/board" element={<ProjectBoardPage />} />
        <Route path="projects/:projectKey/sprints" element={<ProjectSprintsPage />} />
        <Route path="projects/:projectKey/reports" element={<ReportsPage />} />
        <Route path="reports" element={<ReportsPage />} />
      </Route>
    </Routes>
  );
}
