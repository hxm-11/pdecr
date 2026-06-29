import { ClipboardCheck, FileText, Inbox, LayoutDashboard } from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { type Item, Main } from "./Main"

const items: Item[] = [
  { icon: LayoutDashboard, title: "Dashboard", path: "/pd-ecr/dashboard" },
  { icon: FileText, title: "PD-ECR", path: "/pd-ecr" },
  { icon: ClipboardCheck, title: "My Tasks", path: "/pd-ecr/tasks" },
  { icon: Inbox, title: "草稿箱", path: "/pd-ecr/drafts" },
]

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-8 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
