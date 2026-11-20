import { Shell } from "@/components/Shell";
export const dynamic = "force-dynamic";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <Shell>{children}</Shell>;
}
