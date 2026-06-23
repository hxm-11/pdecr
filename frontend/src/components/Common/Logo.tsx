import { Link } from "@tanstack/react-router"

import { useTheme } from "@/components/theme-provider"
import { cn } from "@/lib/utils"
// 删掉没用的fastapi图标
import logo from "/assets/images/Bosch.svg"
import logoLight from "/assets/images/Bosch.svg"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const fullLogo = isDark ? logoLight : logo
  const iconLogo = logo // 折叠也用Bosch，不用fastapi

  const content =
    variant === "responsive" ? (
      <>
        {/* PNG必须加 object-contain，防止拉伸变形，h-9放大 */}
        <img
          src={fullLogo}
          alt="Bosch"
          className={cn(
            "h-25 w-50 object-contain group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        {/* 折叠时用Bosch小图标，size-7放大 */}
        <img
          src={iconLogo}
          alt="Bosch"
          className={cn(
            "size-7 object-contain hidden group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={variant === "full" ? fullLogo : iconLogo}
        alt="Bosch"
        className={cn(
          variant === "full"
            ? "h-9 w-auto object-contain"
            : "size-7 object-contain",
          className,
        )}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
