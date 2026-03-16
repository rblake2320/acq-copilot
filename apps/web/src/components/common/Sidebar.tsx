"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  MessageSquare,
  Calculator,
  BookOpen,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  Building2,
  Shield,
  Zap,
  DollarSign,
  LogIn,
  LogOut,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { sidebarOpen, toggleSidebar, user, logout } = useStore();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

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
      name: "FAR Search",
      href: "/far-search",
      icon: BookOpen,
      description: "Semantic search over FAR and DFARS regulations",
    },
    {
      name: "Opportunities",
      href: "/opportunities",
      icon: Building2,
      description: "Search active SAM.gov contract opportunities",
    },
    {
      name: "Compliance",
      href: "/compliance",
      icon: Shield,
      description: "FAR/DFARS clause compliance checker for solicitations",
    },
    {
      name: "Planning",
      href: "/planning",
      icon: Zap,
      description: "Acquisition strategy, thresholds, and contract vehicle recommendations",
    },
    {
      name: "Price Analysis",
      href: "/pricing",
      icon: DollarSign,
      description: "Price reasonableness analysis using BLS OEWS and GSA CALC+ data",
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

        {/* Footer — user info / auth */}
        <div className="border-t border-border p-3 dark:border-border">
          {user ? (
            /* Logged-in state */
            sidebarOpen ? (
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <User className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-foreground">
                      {user.username}
                    </p>
                    <Badge variant="secondary" className="mt-0.5 px-1 py-0 text-[10px]">
                      {user.role}
                    </Badge>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  title="Sign out"
                  className="flex-shrink-0 text-muted-foreground hover:text-foreground"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              /* Collapsed — just icon + logout on hover */
              <div className="group relative flex justify-center">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <User className="h-4 w-4" />
                </div>
                <button
                  onClick={handleLogout}
                  title={`Sign out (${user.username})`}
                  className="absolute inset-0 flex items-center justify-center rounded-full opacity-0 transition-opacity group-hover:bg-destructive/10 group-hover:opacity-100"
                >
                  <LogOut className="h-3.5 w-3.5 text-destructive" />
                </button>
              </div>
            )
          ) : (
            /* Guest state */
            sidebarOpen ? (
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">Guest</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push("/login")}
                  className="h-7 gap-1 px-2 text-xs"
                >
                  <LogIn className="h-3.5 w-3.5" />
                  Login
                </Button>
              </div>
            ) : (
              <div className="flex justify-center">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => router.push("/login")}
                  title="Login"
                  className="text-muted-foreground hover:text-foreground"
                >
                  <LogIn className="h-4 w-4" />
                </Button>
              </div>
            )
          )}
          {sidebarOpen && (
            <p className="mt-2 text-[10px] text-muted-foreground/60">
              v0.1.0 Beta
            </p>
          )}
        </div>
      </div>
    </aside>
  );
}
