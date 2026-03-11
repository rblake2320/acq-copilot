"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { CheckCircle, AlertCircle, Clock, Zap, RefreshCw, Loader2, KeyRound } from "lucide-react";
import { apiClient } from "@/lib/api";
import { ToolHealthStatus, APIKeyStatus, CacheStats, AuditEvent } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatDate } from "@/lib/format";

// Known services — shown even when the backend returns no API key data
const KNOWN_SERVICES = [
  { name: "Anthropic", description: "Claude AI — chat and analysis" },
  { name: "OpenAI", description: "GPT models — fallback generation" },
  { name: "BLS", description: "Bureau of Labor Statistics — wage data" },
  { name: "Regulations.gov", description: "Federal regulatory documents" },
  { name: "GSA Per Diem", description: "GSA travel per diem rates" },
];

export default function AdminPage() {
  // Track per-service verify results: null = not verified, true = valid, false = invalid
  const [verifyResults, setVerifyResults] = useState<Record<string, boolean | null>>({});
  const [verifyingService, setVerifyingService] = useState<string | null>(null);

  const handleVerify = async (serviceName: string) => {
    setVerifyingService(serviceName);
    try {
      const res = await apiClient.admin.verifyAPIKey(serviceName);
      setVerifyResults((prev) => ({ ...prev, [serviceName]: res.valid }));
    } catch {
      setVerifyResults((prev) => ({ ...prev, [serviceName]: false }));
    } finally {
      setVerifyingService(null);
    }
  };

  const { data: toolHealth = [], isLoading: toolsLoading } = useQuery({
    queryKey: ["tool-health"],
    queryFn: () => apiClient.admin.getToolHealth(),
  });

  const { data: apiKeys = [] } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => apiClient.admin.getAPIKeyStatus(),
  });

  const { data: cacheStats } = useQuery({
    queryKey: ["cache-stats"],
    queryFn: () => apiClient.admin.getCacheStats(),
  });

  const { data: auditLog = [] } = useQuery({
    queryKey: ["audit-log"],
    queryFn: () => apiClient.admin.getAuditLog(50),
  });

  const clearCacheMutation = useMutation({
    mutationFn: () => apiClient.admin.clearCache(),
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "valid":
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "degraded":
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      case "expired":
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      case "error":
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      case "invalid":
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Clock className="h-5 w-5 text-blue-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
      case "valid":
        return "bg-green-500/10 text-green-700 dark:text-green-400";
      case "degraded":
      case "expired":
        return "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400";
      case "error":
      case "invalid":
        return "bg-red-500/10 text-red-700 dark:text-red-400";
      default:
        return "bg-blue-500/10 text-blue-700 dark:text-blue-400";
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground dark:text-foreground">
            System Administration
          </h1>
          <p className="mt-2 text-muted-foreground dark:text-muted-foreground">
            Monitor tool health, API configuration, and system metrics
          </p>
        </div>
        <Button
          onClick={() => clearCacheMutation.mutate()}
          disabled={clearCacheMutation.isPending}
          className="gap-2 dark:hover:bg-primary/80"
        >
          {clearCacheMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Clear Cache
        </Button>
      </div>

      {/* Overview Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Tools Healthy
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {toolHealth.filter((t) => t.status === "healthy").length}/{toolHealth.length}
            </div>
            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
              All operational
            </p>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              API Keys
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {apiKeys.filter((k) => k.status === "valid").length}/{apiKeys.length}
            </div>
            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
              Configured & valid
            </p>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Cache Hit Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {cacheStats ? `${Math.round(cacheStats.hitRate * 100)}%` : "—"}
            </div>
            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
              {cacheStats ? `${cacheStats.totalRequests} requests` : "No data"}
            </p>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Cache Size
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {cacheStats ? `${(cacheStats.cacheSize / 1024 / 1024).toFixed(1)} MB` : "—"}
            </div>
            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
              {cacheStats ? `${cacheStats.evictions} evictions` : "No data"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="tools" className="space-y-4">
        <TabsList className="dark:bg-muted">
          <TabsTrigger value="tools">Tool Health</TabsTrigger>
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="audit">Audit Log</TabsTrigger>
        </TabsList>

        {/* Tool Health Tab */}
        <TabsContent value="tools" className="space-y-3">
          {toolsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid gap-3">
              {toolHealth.map((tool: ToolHealthStatus) => (
                <Card key={tool.toolName} className="dark:bg-card">
                  <CardContent className="flex items-center justify-between py-4">
                    <div className="flex items-center gap-4">
                      {getStatusIcon(tool.status)}
                      <div>
                        <h4 className="font-semibold text-foreground dark:text-foreground">
                          {tool.toolName}
                        </h4>
                        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                          Response: {tool.responseTime}ms • Success rate:{" "}
                          {Math.round(tool.successRate * 100)}%
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant="secondary"
                        className={getStatusColor(tool.status)}
                      >
                        {tool.status}
                      </Badge>
                      {tool.errorCount > 0 && (
                        <Badge variant="destructive" className="bg-red-500/10 text-red-700 dark:text-red-400">
                          {tool.errorCount} errors
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* API Keys Tab */}
        <TabsContent value="api-keys" className="space-y-3">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Configured Services</CardTitle>
              <CardDescription>
                API keys are managed via server environment variables. Use Verify to test each key.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {KNOWN_SERVICES.map((svc) => {
                const verified = verifyResults[svc.name];
                const isVerifying = verifyingService === svc.name;
                // Also check if the backend returned status for this service
                const backendKey = apiKeys.find((k: APIKeyStatus) => k.service === svc.name);
                const status = backendKey
                  ? backendKey.configured
                    ? backendKey.status
                    : "Not configured"
                  : verified === null || verified === undefined
                  ? "Not configured"
                  : verified
                  ? "valid"
                  : "invalid";

                return (
                  <div
                    key={svc.name}
                    className="flex items-center justify-between rounded-lg border border-border p-4 dark:border-border"
                  >
                    <div className="flex items-center gap-3">
                      <KeyRound className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <h4 className="font-semibold text-foreground dark:text-foreground">
                          {svc.name}
                        </h4>
                        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                          {svc.description}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant="secondary"
                        className={
                          verified === true || status === "valid"
                            ? "bg-green-500/10 text-green-700 dark:text-green-400"
                            : verified === false || status === "invalid"
                            ? "bg-red-500/10 text-red-700 dark:text-red-400"
                            : "bg-muted text-muted-foreground"
                        }
                      >
                        {verified === true
                          ? "valid"
                          : verified === false
                          ? "invalid"
                          : status}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isVerifying}
                        onClick={() => handleVerify(svc.name)}
                        className="gap-1 dark:border-border"
                      >
                        {isVerifying ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <CheckCircle className="h-3 w-3" />
                        )}
                        Verify
                      </Button>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Log Tab */}
        <TabsContent value="audit" className="space-y-3">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Recent Activity</CardTitle>
              <CardDescription>Last 50 audit events</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {auditLog.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground dark:text-muted-foreground">
                    No audit events
                  </p>
                ) : (
                  auditLog.map((event: AuditEvent) => (
                    <div
                      key={event.id}
                      className="flex items-center justify-between border-b border-border pb-2 last:border-0 dark:border-border"
                    >
                      <div className="text-sm">
                        <p className="font-medium text-foreground dark:text-foreground">
                          {event.action}
                        </p>
                        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                          {event.resource}: {event.resourceId}
                        </p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground dark:text-muted-foreground">
                        <p>{formatDate(new Date(event.timestamp))}</p>
                        <p>{event.ipAddress}</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
