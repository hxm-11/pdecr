import { Link as RouterLink, useRouterState } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

export type Item = {
  icon: LucideIcon;
  title: string;
  path: string;
};

interface MainProps {
  items: Item[];
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar();
  const router = useRouterState();
  const currentPath = router.location.pathname;

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            const isActive =
              currentPath === item.path ||
              (item.path !== "/pd-ecr" && currentPath.startsWith(item.path));

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  className="relative h-9 rounded-md px-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 data-[active=true]:bg-blue-50 data-[active=true]:text-blue-700 data-[active=true]:font-semibold data-[active=true]:shadow-[inset_3px_0_0_#2563eb] [&>svg]:size-4"
                  asChild
                >
                  <RouterLink to={item.path} onClick={handleMenuClick}>
                    <item.icon />
                    <span>{item.title}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
