import { ReactNode } from "react";
import AppShell from "./shell/AppShell";

interface AppProps {
  children: ReactNode;
}

export default function App({ children }: AppProps) {
  return <AppShell>{children}</AppShell>;
}
