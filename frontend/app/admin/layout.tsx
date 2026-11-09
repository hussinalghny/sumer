import { AdminShell } from "@/components/admin/Shell";

export const metadata = { title: "سومر · لوحة التحكم", robots: { index: false, follow: false } };

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
