"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  Calculator,
  BookOpen,
  Search,
  TrendingUp,
  Clock,
  ArrowRight,
  Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Dashboard() {
  const router = useRouter();

  const quickActions = [
    {
      icon: MessageSquare,
      title: "Start Acquisition Chat",
      description: "Ask questions about federal procurement, regulations, and best practices",
      href: "/chat",
      color: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    },
    {
      icon: Calculator,
      title: "Create IGCE",
      description: "Build an Independent Government Cost Estimate with dynamic labor and travel categories",
      href: "/igce",
      color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    },
    {
      icon: BookOpen,
      title: "Explore Regulations",
      description: "Search Federal Register, eCFR, and Regulations.gov for compliance requirements",
      href: "/regulatory",
      color: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
    },
    {
      icon: Search,
      title: "Market Research",
      description: "Analyze awards from USASpending and competitive intelligence by NAICS/PSC",
      href: "/market-research",
      color: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
    },
    {
      icon: BookOpen,
      title: "FAR/DFARS Search",
      description: "Semantic search over all 53 FAR parts",
      href: "/far-search",
      color: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
    },
    {
      icon: Building2,
      title: "Opportunities",
      description: "Search active SAM.gov contract opportunities",
      href: "/opportunities",
      color: "bg-emerald-500/10 text-emerald-400",
    },
  ];

  const stats = [
    { label: "API Endpoints", value: "12", icon: TrendingUp },
    { label: "Tools Available", value: "8", icon: Clock },
    { label: "System Status", value: "Healthy", icon: MessageSquare },
  ];

  return (
    <div className="space-y-8 p-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-4xl font-bold text-foreground dark:text-foreground">
          Acquisition Copilot
        </h1>
        <p className="text-lg text-muted-foreground dark:text-muted-foreground">
          Your intelligent assistant for federal acquisition intelligence, cost estimation, and market research
        </p>
      </div>

      {/* Quick Action Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {quickActions.map((action) => {
          const Icon = action.icon;
          return (
            <Card
              key={action.href}
              className="cursor-pointer transition-all hover:shadow-lg dark:hover:shadow-lg"
              onClick={() => router.push(action.href)}
            >
              <CardHeader>
                <div className={`mb-4 inline-block rounded-lg p-3 ${action.color}`}>
                  <Icon className="h-6 w-6" />
                </div>
                <CardTitle className="dark:text-foreground">{action.title}</CardTitle>
                <CardDescription>{action.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  variant="ghost"
                  className="gap-2 p-0 text-primary dark:text-primary hover:gap-3 dark:hover:bg-transparent"
                >
                  Get started
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label} className="dark:bg-card/50">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium dark:text-foreground">
                  {stat.label}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground dark:text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-foreground dark:text-foreground">
                  {stat.value}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Info Card */}
      <Card className="bg-primary/5 dark:bg-primary/10">
        <CardHeader>
          <CardTitle className="dark:text-foreground">Getting Started</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground dark:text-muted-foreground">
          <p>
            Acquisition Copilot provides AI-powered assistance for federal acquisition professionals:
          </p>
          <ul className="list-inside list-disc space-y-1 pl-2">
            <li>Cost estimation with IGCE builder supporting labor escalation and travel modeling</li>
            <li>Regulatory compliance tracking across FR, eCFR, and Regulations.gov</li>
            <li>Market research using USASpending data with NAICS and PSC filtering</li>
            <li>AI chat assistant trained on acquisition best practices and regulations</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
