import Sidebar from "@/components/Sidebar";
import Surface from "@/components/Surface";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Surface>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex w-full flex-col px-6 py-10 lg:ml-[88px] lg:px-12">
          {children}
        </main>
      </div>
    </Surface>
  );
}
