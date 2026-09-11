import {
  BarChart3,
  BriefcaseBusiness,
  CalendarDays,
  Columns3,
  LayoutDashboard,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

type NavigationSection = "overview" | "projects" | "sprints" | "board" | "reports";

const navigationItems = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "projects", label: "Projects", icon: BriefcaseBusiness },
  { id: "sprints", label: "Sprints", icon: CalendarDays },
  { id: "board", label: "Board", icon: Columns3 },
  { id: "reports", label: "Reports", icon: BarChart3 },
] as const satisfies ReadonlyArray<{
  id: NavigationSection;
  label: string;
  icon: typeof LayoutDashboard;
}>;

function getProjectRoute(pathname: string) {
  return pathname.match(/^\/projects\/([^/]+)(?:\/(board|sprints|reports))?\/?$/);
}

function getActiveSection(pathname: string): NavigationSection {
  if (pathname === "/projects" || pathname === "/projects/") return "projects";
  if (pathname === "/reports" || pathname === "/reports/") return "reports";

  const projectRoute = getProjectRoute(pathname);
  if (!projectRoute) return "overview";

  switch (projectRoute[2]) {
    case "board":
      return "board";
    case "sprints":
      return "sprints";
    case "reports":
      return "reports";
    default:
      return "overview";
  }
}

function navigationClassName(isActive: boolean, mobile = false) {
  const base = "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors";
  if (mobile) {
    return `${base} ${
      isActive
        ? "bg-slate-100 text-slate-900"
        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
    }`;
  }
  return `${base} ${
    isActive
      ? "bg-slate-800 text-white"
      : "text-slate-300 hover:bg-slate-800/70 hover:text-white"
  }`;
}

function NavigationLinks({ mobile = false }: { mobile?: boolean }) {
  const { pathname } = useLocation();
  const projectRoute = getProjectRoute(pathname);
  const projectKey = projectRoute?.[1];
  const activeSection = getActiveSection(pathname);
  const projectBasePath = projectKey ? `/projects/${projectKey}` : undefined;
  const destinations: Record<NavigationSection, string> = {
    overview: projectBasePath ?? "/",
    projects: "/projects",
    sprints: projectBasePath ? `${projectBasePath}/sprints` : "/projects",
    board: projectBasePath ? `${projectBasePath}/board` : "/projects",
    reports: projectBasePath ? `${projectBasePath}/reports` : "/reports",
  };

  return (
    <>
      {navigationItems.map(({ id, icon: Icon, label }) => (
        <NavLink
          key={id}
          to={destinations[id]}
          className={() => navigationClassName(activeSection === id, mobile)}
        >
          <Icon className="size-4" aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </>
  );
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden h-screen w-60 flex-col overflow-y-auto border-r border-slate-800 bg-slate-950 px-3 py-5 md:flex">
      <div className="px-3 pb-7">
        <p className="text-sm font-semibold tracking-tight text-white">Sprint Intelligence</p>
        <p className="mt-1 text-xs text-slate-400">Delivery workspace</p>
      </div>
      <nav className="space-y-1" aria-label="Primary navigation">
        <NavigationLinks />
      </nav>
      <div className="mt-auto rounded-lg border border-slate-800 bg-slate-900/70 p-3">
        <p className="text-xs font-medium text-slate-200">Workspace foundation</p>
        <p className="mt-1 text-xs leading-5 text-slate-400">Project data and workflow views will be added incrementally.</p>
      </div>
    </aside>
  );
}

export function MobileNavigation() {
  return (
    <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 py-2 md:hidden" aria-label="Mobile navigation">
      <NavigationLinks mobile />
    </nav>
  );
}
