import { ReactNode } from "react";
import { Header } from "./Header";
import { Sparky } from "@/components/Sparky";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen min-h-0 flex-col bg-slate-50/40">
      <Header />
      <main className="flex flex-1 min-h-0 overflow-hidden">{children}</main>
      <Sparky />
    </div>
  );
}
