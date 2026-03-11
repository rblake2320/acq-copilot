import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Sidebar } from "@/components/common/Sidebar";
import { Providers } from "@/components/Providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Acquisition Copilot",
  description:
    "Federal acquisition intelligence platform for IGCE, regulatory analysis, and market research",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          <div className="flex min-h-screen bg-background text-foreground dark:bg-background dark:text-foreground">
            <Sidebar />
            <main className="ml-20 flex-1 transition-all duration-300 lg:ml-64">
              <div className="h-full w-full">{children}</div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
