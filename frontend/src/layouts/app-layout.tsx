import { CircleUserRound } from "lucide-react";
import { Outlet } from "react-router-dom";

import { MobileNavigation, Sidebar } from "../components/sidebar";

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      <div className="min-w-0 md:ml-60">
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-7">
          <div>
            <p className="text-sm font-semibold text-slate-900 md:hidden">Sprint Intelligence</p>
            <p className="text-sm font-medium text-slate-800">Workspace</p>
            <p className="text-xs text-slate-500">Project delivery overview</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-slate-800">Team member</p>
              <p className="text-xs text-slate-500">Demo workspace</p>
            </div>
            <div className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-600">
              <CircleUserRound className="size-5" aria-hidden="true" />
            </div>
          </div>
        </header>
        <MobileNavigation />
        <main className="p-4 sm:p-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
