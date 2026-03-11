"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Loader2,
  KeyRound,
  Eye,
  EyeOff,
  Save,
  ChevronDown,
  ChevronUp,
  Download,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { ToolHealthStatus, APIKeyStatus, AuditEvent } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";

// All known services with their backend key names and labels
const KNOWN_SERVICES = [
  { id: "anthropic",       label: "Anthropic",         description: "Claude AI — chat and analysis" },
  { id: "openai",          label: "OpenAI",             description: "GPT models — fallback generation" },
  { id: "bls",             label: "BLS",                description: "Bureau of Labor Statistics — wage data" },
  { id: "regulations_gov", label: "Regulations.gov",    description: "Federal regulatory documents" },
  { id: "gsa_perdiem",     label: "GSA Per Diem",       description: "GSA travel per diem rates" },
  { id: "congress_gov",    label: "Congress.gov",       description: "Congressional data and legislation" },
  { id: "census",          label: "Census API",         description: "US Census Bureau data" },
];

export default function AdminPage() {
  const queryClient = useQueryClient();

  // Verify state: null = not checked, true = configured, false = not configured
  const [verifyResults, setVerifyResults] = useState<Record<string, boolean | null>>({});
  const [verifyingService, setVerifyingService] = useState<string | null>(null);

  // Key input state per service
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, "idle" | "saving" | "saved" | "error">>({});

  const handleVerify = async (serviceId: string) => {
    setVerifyingService(serviceId);
    try {
      const res = await apiClient.admin.verifyAPIKey(serviceId);
      setVerifyResults((prev) => ({ ...prev, [serviceId]: res.valid }));
    } catch {
      setVerifyResults((prev) => ({ ...prev, [serviceId]: false }));
    } finally {
      setVerifyingService(null);
    }
  };

  const handleSaveKey = async (serviceId: string) => {
    const key = keyInputs[serviceId]?.trim();
    if (!key) return;
    setSaveStatus((prev) => ({ ...prev, [serviceId]: "saving" }));
    try {
      await apiClient.admin.setAPIKey(serviceId, key);
      setSaveStatus((prev) => ({ ...prev, [serviceId]: "saved" }));
      setVerifyResults((prev) => ({ ...prev, [serviceId]: true }));
      // Refresh key status
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setTimeout(() => setSaveStatus((prev) => ({ ...prev, [serviceId]: "idle" })), 3000);
    } catch {
      setSaveStatus((prev) => ({ ...prev, [serviceId]: "error" }));
      setTimeout(() => setSaveStatus((prev) => ({ ...prev, [serviceId]: "idle" })), 3000);
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

  // Auto-verify all services on page load
  useEffect(() => {
    if (apiKeys.length === 0) return;
    const run = async () => {
      const results: Record<string, boolean> = {};
      await Promise.allSettled(
        KNOWN_SERVICES.map(async (svc) => {
          try {
            const res = await apiClient.admin.verifyAPIKey(svc.id);
            results[svc.id] = res.valid;
          } catch {
            results[svc.id] = false;
          }
        })
      );
      setVerifyResults(results);
    };
    run();
  }, [apiKeys.length]);

  const { data: trainingStats } = useQuery({
    queryKey: ["training-stats"],
    queryFn: () => apiClient.admin.getTrainingStats(),
    refetchInterval: 30000,
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

  const getStatusIcon = (st: string) => {
    if (st === "healthy" || st === "valid" || st === "saved") return <CheckCircle className="h-5 w-5 text-green-500" />;
    if (st === "degraded" || st === "expired") return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    if (st === "error" || st === "invalid") return <AlertCircle className="h-5 w-5 text-red-500" />;
    return <Clock className="h-5 w-5 text-blue-500" />;
  };

  const getStatusColor = (st: string) => {
    if (st === "healthy" || st === "valid") return "bg-green-500/10 text-green-700 dark:text-green-400";
    if (st === "degraded" || st === "expired") return "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400";
    if (st === "error" || st === "invalid") return "bg-red-500/10 text-red-700 dark:text-red-400";
    return "bg-muted text-muted-foreground";
  };

  // Merge backend data + verify results into a single status string per service
  const getServiceStatus = (serviceId: string): string => {
    const verified = verifyResults[serviceId];
    if (verified === true) return "valid";
    if (verified === false) return "not configured";
    const backendKey = apiKeys.find((k: APIKeyStatus) => k.service === serviceId);
    if (backendKey) return backendKey.configured ? "valid" : "unconfigured";
    return "unconfigured";
  };

  const configuredCount = KNOWN_SERVICES.filter(
    (s) => getServiceStatus(s.id) === "valid"
  ).length;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">System Administration</h1>
          <p className="mt-2 text-muted-foreground">
            Monitor tool health, API configuration, and system metrics
          </p>
        </div>
        <Button
          onClick={() => clearCacheMutation.mutate()}
          disabled={clearCacheMutation.isPending}
          className="gap-2"
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
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Tools Healthy</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {toolsLoading
                ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                : toolHealth.length === 0
                ? "-/-"
                : `${toolHealth.filter((t) => t.status === "healthy").length}/${toolHealth.length}`}
            </div>
            <p className="text-xs text-muted-foreground">API tools operational</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">API Keys</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {configuredCount}/{KNOWN_SERVICES.length}
            </div>
            <p className="text-xs text-muted-foreground">Configured</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Cache Hit Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {cacheStats ? `${Math.round(cacheStats.hitRate * 100)}%` : "—"}
            </div>
            <p className="text-xs text-muted-foreground">
              {cacheStats ? `${cacheStats.totalRequests} requests` : "No data"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Cache Size</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {cacheStats ? `${(cacheStats.cacheSize / 1024 / 1024).toFixed(1)} MB` : "—"}
            </div>
            <p className="text-xs text-muted-foreground">
              {cacheStats ? `${cacheStats.evictions} evictions` : "No data"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="api-keys" className="space-y-4">
        <TabsList>
          <TabsTrigger value="tools">Tool Health</TabsTrigger>
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="training">Training Data</TabsTrigger>
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
                <Card key={tool.toolName}>
                  <CardContent className="flex items-center justify-between py-4">
                    <div className="flex items-center gap-4">
                      {getStatusIcon(tool.status)}
                      <div>
                        <h4 className="font-semibold">{tool.toolName}</h4>
                        <p className="text-xs text-muted-foreground">
                          Response: {tool.responseTime}ms · Success: {Math.round(tool.successRate * 100)}%
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant="secondary" className={getStatusColor(tool.status)}>
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
          <Card>
            <CardHeader>
              <CardTitle>API Key Management</CardTitle>
              <CardDescription>
                Verify existing keys or paste a new key to load it into the running server. Keys set here
                are active immediately but reset on server restart — add them to <code>.env</code> to make
                them permanent.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {KNOWN_SERVICES.map((svc) => {
                const st = getServiceStatus(svc.id);
                const isVerifying = verifyingService === svc.id;
                const saving = saveStatus[svc.id] ?? "idle";
                const isExpanded = expanded[svc.id] ?? false;
                const keyVal = keyInputs[svc.id] ?? "";
                const masked = showKey[svc.id] ? keyVal : keyVal.replace(/./g, "•");

                return (
                  <div
                    key={svc.id}
                    className="rounded-lg border border-border overflow-hidden"
                  >
                    {/* Header row */}
                    <div className="flex items-center justify-between p-4">
                      <div className="flex items-center gap-3">
                        <KeyRound className="h-5 w-5 text-muted-foreground shrink-0" />
                        <div>
                          <h4 className="font-semibold">{svc.label}</h4>
                          <p className="text-xs text-muted-foreground">{svc.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="secondary"
                          className={
                            st === "valid"
                              ? "bg-green-500/10 text-green-700 dark:text-green-400"
                              : st === "not configured" || st === "unconfigured"
                              ? "bg-muted text-muted-foreground"
                              : "bg-red-500/10 text-red-700 dark:text-red-400"
                          }
                        >
                          {st}
                        </Badge>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isVerifying}
                          onClick={() => handleVerify(svc.id)}
                          className="gap-1 text-xs"
                        >
                          {isVerifying ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3 w-3" />
                          )}
                          Verify
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setExpanded((prev) => ({ ...prev, [svc.id]: !isExpanded }))}
                          className="gap-1 text-xs"
                        >
                          {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                          {isExpanded ? "Cancel" : "Load Key"}
                        </Button>
                      </div>
                    </div>

                    {/* Expandable key input */}
                    {isExpanded && (
                      <div className="border-t border-border bg-muted/30 p-4 flex items-center gap-2">
                        <div className="relative flex-1">
                          <Input
                            type={showKey[svc.id] ? "text" : "password"}
                            placeholder={`Paste your ${svc.label} API key…`}
                            value={keyVal}
                            onChange={(e) =>
                              setKeyInputs((prev) => ({ ...prev, [svc.id]: e.target.value }))
                            }
                            className="pr-10 font-mono text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => setShowKey((prev) => ({ ...prev, [svc.id]: !prev[svc.id] }))}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showKey[svc.id] ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                        <Button
                          size="sm"
                          disabled={!keyVal.trim() || saving === "saving"}
                          onClick={() => handleSaveKey(svc.id)}
                          className="gap-1 shrink-0"
                        >
                          {saving === "saving" ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : saving === "saved" ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : (
                            <Save className="h-3 w-3" />
                          )}
                          {saving === "saving" ? "Saving…" : saving === "saved" ? "Saved!" : saving === "error" ? "Error" : "Save"}
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Training Data Tab */}
        <TabsContent value="training" className="space-y-4">
          {/* Stats row */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" /> Conversations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{trainingStats?.total_conversations ?? "—"}</div>
                <p className="text-xs text-muted-foreground">{trainingStats?.exportable_conversations ?? 0} exportable</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Messages</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{trainingStats?.total_messages ?? "—"}</div>
                <p className="text-xs text-muted-foreground">Across all conversations</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <ThumbsUp className="h-4 w-4 text-green-500" /> Thumbs Up
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{trainingStats?.thumbs_up ?? 0}</div>
                <p className="text-xs text-muted-foreground">High-quality responses</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <ThumbsDown className="h-4 w-4 text-red-500" /> Thumbs Down
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{trainingStats?.thumbs_down ?? 0}</div>
                <p className="text-xs text-muted-foreground">Needs improvement</p>
              </CardContent>
            </Card>
          </div>

          {/* Export card */}
          <Card>
            <CardHeader>
              <CardTitle>Export Training Data</CardTitle>
              <CardDescription>
                Download conversation history as JSONL for fine-tuning. Each line contains a complete
                conversation in Anthropic fine-tuning format:{" "}
                <code className="text-xs">{"{"}"messages": [...]{"}"}</code>.
                Rate responses with 👍/👎 in the Chat view — then use the rated-only export to
                build a curated, high-quality training set.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <a href={apiClient.admin.exportTrainingData(false)} download>
                <Button variant="outline" className="gap-2">
                  <Download className="h-4 w-4" />
                  Export All Conversations
                </Button>
              </a>
              <a href={apiClient.admin.exportTrainingData(true)} download>
                <Button className="gap-2">
                  <ThumbsUp className="h-4 w-4" />
                  Export Thumbs-Up Only
                </Button>
              </a>
            </CardContent>
          </Card>

          {/* How-to */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">How to Use for Model Improvement</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <div className="flex gap-3">
                <span className="font-mono text-primary font-bold">1.</span>
                <span>Chat with the system — every conversation is automatically saved to the database.</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-primary font-bold">2.</span>
                <span>Rate responses with 👍 (good) or 👎 (needs work) using the buttons below each AI reply.</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-primary font-bold">3.</span>
                <span>Click <strong>Export Thumbs-Up Only</strong> to download a curated JSONL file of your best examples.</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-primary font-bold">4.</span>
                <span>Use the JSONL with Anthropic fine-tuning, OpenAI fine-tuning, or any RLHF pipeline that accepts message-format data.</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Log Tab */}
        <TabsContent value="audit" className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Last 50 audit events</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {auditLog.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">No audit events</p>
                ) : (
                  auditLog.map((event: AuditEvent) => (
                    <div
                      key={event.id}
                      className="flex items-center justify-between border-b border-border pb-2 last:border-0"
                    >
                      <div className="text-sm">
                        <p className="font-medium">{event.action}</p>
                        <p className="text-xs text-muted-foreground">
                          {event.resource}: {event.resourceId}
                        </p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
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
