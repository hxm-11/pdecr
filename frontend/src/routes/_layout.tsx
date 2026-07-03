import {
  createFileRoute,
  Outlet,
  redirect,
  useLocation,
} from "@tanstack/react-router";
import { Bell, CircleHelp, Search } from "lucide-react";

import AppSidebar from "@/components/Sidebar/AppSidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { UsersService } from "@/client";
import { isLoggedIn } from "@/hooks/useAuth";
import { clearAccessToken } from "@/lib/authToken";

export const Route = createFileRoute("/_layout")({
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" });
    }
    try {
      await UsersService.readUserMe();
    } catch {
      clearAccessToken();
      throw redirect({ to: "/login" });
    }
  },
  component: Layout,
});

function topbarPageLabel(pathname: string) {
  if (pathname === "/pd-ecr" || pathname === "/pd-ecr/new") return "New Change";
  if (pathname.startsWith("/pd-ecr/tasks")) return "My Tasks";
  if (pathname.startsWith("/pd-ecr/cases")) return "Cases";
  if (pathname.startsWith("/pd-ecr/dashboard")) return "Dashboard";
  if (pathname.startsWith("/pd-ecr/history-case")) return "History";
  if (pathname.startsWith("/pd-ecr/drafts")) return "Drafts";
  if (pathname.startsWith("/pd-ecr/content")) return "Change Content";
  if (pathname.startsWith("/pd-ecr/documents")) return "Document";
  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/admin")) return "Admin";
  return "Workspace";
}

function Layout() {
  const { pathname } = useLocation();
  const pageLabel = topbarPageLabel(pathname);

  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar />
      <SidebarInset className="h-svh min-w-0 overflow-hidden">
        <header className="z-10 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 text-sm text-slate-600">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <span className="truncate font-semibold text-slate-900">PD-ECR</span>
            <span className="text-slate-300">/</span>
            <span className="truncate text-slate-500">{pageLabel}</span>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <label className="relative hidden min-w-72 lg:block">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Search case, owner, part no."
                className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-9 pr-3 text-sm outline-none transition focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100"
              />
            </label>
            <button
              type="button"
              className="flex size-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
              aria-label="Help"
            >
              <CircleHelp className="size-4" />
            </button>
            <button
              type="button"
              className="flex size-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
              aria-label="Notifications"
            >
              <Bell className="size-4" />
            </button>
          </div>
        </header>
        <main className="flex min-h-0 flex-1 overflow-y-auto bg-slate-50 p-3 md:p-4">
          <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default Layout;
