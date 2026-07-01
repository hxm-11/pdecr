import { Appearance } from "@/components/Common/Appearance";
import { Logo } from "@/components/Common/Logo";
import { useTheme } from "@/components/theme-provider";
import { useEffect } from "react";
import { Footer } from "./Footer";

interface AuthLayoutProps {
  children: React.ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme("light");
  }, [setTheme]);

  return (
    <div className="grid min-h-svh bg-slate-50 text-slate-900 lg:grid-cols-[minmax(30rem,1fr)_minmax(32rem,0.9fr)]">
      <div className="relative hidden overflow-hidden border-r border-slate-200 bg-white lg:flex lg:items-center lg:justify-center">
        <div className="absolute left-0 top-0 h-1 w-full bg-red-600" />
        <div className="flex flex-col items-center gap-5">
          <Logo variant="full" className="h-16" asLink={false} />
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-900">
              BOSCH PD-ECR Management
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Engineering change workflow cockpit
            </p>
          </div>
        </div>
      </div>
      <div className="flex min-h-svh flex-col gap-4 bg-slate-50 p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  );
}
