"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Calculator,
  BookOpen,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useStore();

  const navigation = [
    {
      name: "Chat",
      href: "/chat",
      icon: MessageSquare,
      description: "Federal acquisition intelligence assistant",
    },
    {
      name: "IGCE Builder",
      href: "/igce",
      icon: Calculator,
      description: "Independent Government Cost Estimate",
    },
    {
      name: "Regulatory",
      href: "/regulatory",
      icon: BookOpen,
      description: "Federal regulations and compliance tracker",
    },
    {
      name: "Market Research",
      href: "/market-research",
      icon: Search,
      description: "USASpending analysis and competitive intelligence",
    },
    {
      name: "Admin",
      href: "/admin",
      icon: Settings,
      description: "System health and configuration",
    },
  ];

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen border-r border-border bg-card transition-all duration-300 dark:border-border dark:bg-card",
        sidebarOpen ? "w-64" : "w-20"
      )}
    >
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-4 dark:border-border">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground dark:bg-primary">
                <span className="text-sm font-bold">AC</span>
              </div>
              <span className="text-lg font-semibold text-foreground dark:text-foreground">
                Acq Copilot
              </span>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="ml-auto dark:hover:bg-accent/10"
          >
            {sidebarOpen ? <ChevronLeft /> : <ChevronRight />}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-2 overflow-y-auto px-3 py-4">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.description}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2 transition-all dark:hover:bg-accent/10",
                  isActive
                    ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary"
                    : "text-muted-foreground hover:text-foreground dark:text-muted-foreground dark:hover:text-foreground"
                )}
              >
                <Icon className="h-5 w-5 flex-shrink-0" />
                {sidebarOpen && (
                  <>
                    <span className="flex-1 text-sm font-medium">
                      {item.name}
                    </span>
                    {isActive && (
                      <div className="h-2 w-2 rounded-full bg-primary dark:bg-primary" />
                    )}
                  </>
                )}
                {!sidebarOpen && (
                  <div className="absolute left-full ml-2 hidden whitespace-nowrap rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground group-hover:block dark:bg-muted">
                    {item.name}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-3 dark:border-border">
          <div className="text-xs text-muted-foreground dark:text-muted-foreground">
            {sidebarOpen && <p>v0.1.0 Beta</p>}
          </div>
        </div>
      </div>
    </aside>
  );
}
