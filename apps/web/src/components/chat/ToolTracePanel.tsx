"use client";

import React, { useState } from "react";
import { ToolRun } from "@/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronUp,
  CheckCircle,
  AlertCircle,
  Clock,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";

interface ToolTracePanelProps {
  toolRuns: ToolRun[];
}

export function ToolTracePanel({ toolRuns }: ToolTracePanelProps) {
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const getStatusIcon = (status: ToolRun["status"]) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "running":
        return <Clock className="h-4 w-4 animate-spin text-blue-500" />;
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusColor = (status: ToolRun["status"]) => {
    switch (status) {
      case "success":
        return "bg-green-500/10 text-green-700 dark:text-green-400";
      case "error":
        return "bg-red-500/10 text-red-700 dark:text-red-400";
      case "running":
        return "bg-blue-500/10 text-blue-700 dark:text-blue-400";
      case "pending":
        return "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400";
    }
  };

  if (toolRuns.length === 0) {
    return (
      <Card className="mx-6 mb-6 border-dashed dark:bg-card/50">
        <CardContent className="py-6 text-center text-sm text-muted-foreground dark:text-muted-foreground">
          No tool runs yet
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mx-6 mb-6 dark:bg-card/50">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary dark:text-primary" />
            <CardTitle className="dark:text-foreground">Tool Trace</CardTitle>
            <Badge variant="secondary" className="ml-2">
              {toolRuns.length}
            </Badge>
          </div>
          <CardDescription className="dark:text-muted-foreground">
            Tool execution details
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {toolRuns.map((run) => (
            <div
              key={run.id}
              className="rounded-lg border border-border bg-background dark:border-border dark:bg-background/50"
            >
              <button
                onClick={() =>
                  setExpandedRun(expandedRun === run.id ? null : run.id)
                }
                className="flex w-full items-center gap-3 p-3 text-left hover:bg-muted/50 dark:hover:bg-muted/20"
              >
                {getStatusIcon(run.status)}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-foreground dark:text-foreground">
                      {run.toolName}
                    </span>
                    <Badge
                      variant="secondary"
                      className={cn(
                        "text-xs",
                        getStatusColor(run.status)
                      )}
                    >
                      {run.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                    {formatDistanceToNow(new Date(run.startedAt), {
                      addSuffix: true,
                    })} • {run.executionTime}ms
                  </p>
                </div>
                {expandedRun === run.id ? <ChevronUp /> : <ChevronDown />}
              </button>

              {expandedRun === run.id && (
                <div className="space-y-3 border-t border-border bg-muted/30 p-3 dark:border-border dark:bg-muted/10">
                  <div>
                    <h4 className="mb-2 text-xs font-semibold text-foreground dark:text-foreground">
                      Input
                    </h4>
                    <pre className="overflow-x-auto rounded bg-background p-2 text-xs text-muted-foreground dark:bg-background dark:text-muted-foreground">
                      {JSON.stringify(run.input, null, 2)}
                    </pre>
                  </div>

                  {run.output && (
                    <div>
                      <h4 className="mb-2 text-xs font-semibold text-foreground dark:text-foreground">
                        Output
                      </h4>
                      <pre className="overflow-x-auto rounded bg-background p-2 text-xs text-muted-foreground dark:bg-background dark:text-muted-foreground">
                        {JSON.stringify(run.output, null, 2)}
                      </pre>
                    </div>
                  )}

                  {run.error && (
                    <div>
                      <h4 className="mb-2 text-xs font-semibold text-red-600 dark:text-red-400">
                        Error
                      </h4>
                      <pre className="overflow-x-auto rounded bg-red-500/10 p-2 text-xs text-red-700 dark:bg-red-500/10 dark:text-red-400">
                        {run.error}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
