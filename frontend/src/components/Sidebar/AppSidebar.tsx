import {
  ClipboardCheck,
  FileText,
  History,
  Inbox,
  LayoutDashboard,
  SquarePen,
} from "lucide-react";

import { SidebarAppearance } from "@/components/Common/Appearance";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar";
import logo from "/assets/images/Bosch.svg";
import { type Item, Main } from "./Main";

const items: Item[] = [
  { icon: SquarePen, title: "New PD-ECR", path: "/pd-ecr" },
  { icon: ClipboardCheck, title: "My tasks", path: "/pd-ecr/tasks" },
  { icon: LayoutDashboard, title: "Dashboard", path: "/pd-ecr/dashboard" },
  { icon: FileText, title: "PD-ECR List", path: "/pd-ecr/cases" },
  { icon: History, title: "History Case", path: "/pd-ecr/history-case" },
  { icon: Inbox, title: "Drafts", path: "/pd-ecr/drafts" },
];

export function AppSidebar() {
  return (
    <Sidebar
      collapsible="none"
      className="h-svh border-r border-slate-200 bg-white"
    >
      <SidebarHeader className="border-b border-slate-100 px-3 py-3">
        <div className="mb-3 h-1 rounded-full bg-red-600" />
        <div className="flex items-center gap-2.5">
          <img src={logo} alt="BOSCH" className="h-8 w-8 object-contain" />
          <div className="min-w-0">
            <p className="truncate text-base font-bold tracking-tight text-slate-900">
              BOSCH
            </p>
            <p className="truncate text-xs font-medium text-slate-500">
              PD-ECR Workspace
            </p>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent className="min-h-0 flex-1 px-2 py-3">
        <p className="px-2.5 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Navigation
        </p>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter className="mt-auto border-t border-slate-100 px-2 py-3">
        <SidebarAppearance />
      </SidebarFooter>
    </Sidebar>
  );
}

export default AppSidebar;
