import {
  Message,
  ChatResponse,
  IGCEInput,
  IGCEOutput,
  ToolHealthStatus,
  AuditEvent,
  AwardResult,
  RegulatoryResult,
  APIKeyStatus,
  CacheStats,
} from "@/types";

const API_BASE = "/api";

class APIClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        error.message || `API request failed: ${response.statusText}`
      );
    }

    return response.json();
  }

  chat = {
    send: async (
      conversationId: string,
      message: string,
      context?: Record<string, unknown>
    ): Promise<ChatResponse> => {
      return this.request<ChatResponse>("/chat/send", {
        method: "POST",
        body: JSON.stringify({ conversationId, message, context }),
      });
    },

    getHistory: async (conversationId: string): Promise<Message[]> => {
      return this.request<Message[]>(`/chat/history/${conversationId}`);
    },

    createConversation: async (title: string): Promise<{ id: string }> => {
      return this.request<{ id: string }>("/chat/conversations", {
        method: "POST",
        body: JSON.stringify({ title }),
      });
    },

    listConversations: async (): Promise<
      Array<{ id: string; title: string; updatedAt: string }>
    > => {
      return this.request("/chat/conversations");
    },
  };

  tools = {
    getStatus: async (): Promise<ToolHealthStatus[]> => {
      return this.request<ToolHealthStatus[]>("/tools/status");
    },

    getInfo: async (toolName: string): Promise<unknown> => {
      return this.request(`/tools/info/${toolName}`);
    },

    executeTrace: async (
      conversationId: string,
      toolName: string,
      input: Record<string, unknown>
    ): Promise<unknown> => {
      return this.request(`/tools/trace`, {
        method: "POST",
        body: JSON.stringify({ conversationId, toolName, input }),
      });
    },
  };

  igce = {
    calculate: async (input: IGCEInput): Promise<IGCEOutput> => {
      return this.request<IGCEOutput>("/igce/calculate", {
        method: "POST",
        body: JSON.stringify(input),
      });
    },

    getHistory: async (): Promise<IGCEOutput[]> => {
      return this.request<IGCEOutput[]>("/igce/history");
    },

    deleteEstimate: async (id: string): Promise<void> => {
      return this.request(`/igce/${id}`, {
        method: "DELETE",
      });
    },

    exportToExcel: async (id: string): Promise<Blob> => {
      const response = await fetch(`${API_BASE}/igce/${id}/export`, {
        method: "GET",
      });

      if (!response.ok) {
        throw new Error("Export failed");
      }

      return response.blob();
    },
  };

  regulatory = {
    search: async (query: string): Promise<RegulatoryResult[]> => {
      return this.request<RegulatoryResult[]>("/regulatory/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
    },

    getFederalRegister: async (query: string): Promise<RegulatoryResult[]> => {
      return this.request<RegulatoryResult[]>("/regulatory/federal-register", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
    },

    getECFR: async (titleNumber: number): Promise<RegulatoryResult[]> => {
      return this.request<RegulatoryResult[]>(
        `/regulatory/ecfr/${titleNumber}`
      );
    },

    getRegulationsGov: async (
      documentType: string
    ): Promise<RegulatoryResult[]> => {
      return this.request<RegulatoryResult[]>(
        `/regulatory/regulations-gov?type=${documentType}`
      );
    },
  };

  marketResearch = {
    searchUSASpending: async (
      query: string,
      filters?: {
        naicsCode?: string;
        pscCode?: string;
        agency?: string;
      }
    ): Promise<AwardResult[]> => {
      return this.request<AwardResult[]>("/market-research/usa-spending", {
        method: "POST",
        body: JSON.stringify({ query, filters }),
      });
    },

    getAwardTrends: async (naicsCode: string): Promise<unknown> => {
      return this.request(`/market-research/trends/${naicsCode}`);
    },

    getCompetitiveAnalysis: async (
      category: string
    ): Promise<Record<string, unknown>> => {
      return this.request(`/market-research/competitive/${category}`);
    },
  };

  admin = {
    getToolHealth: async (): Promise<ToolHealthStatus[]> => {
      const raw = await this.request<{
        total_tools: number;
        health_checks: Record<string, { tool_id: string; status: string; message: string }>;
      }>("/admin/tools/status");
      return Object.values(raw.health_checks).map((h) => ({
        toolName: h.tool_id,
        status: h.status === "healthy" ? "healthy" : "error",
        responseTime: 0,
        lastChecked: new Date(),
        errorCount: h.status === "healthy" ? 0 : 1,
        successRate: h.status === "healthy" ? 1.0 : 0.0,
      }));
    },

    getAPIKeyStatus: async (): Promise<APIKeyStatus[]> => {
      const raw = await this.request<{
        api_keys: Record<string, { configured: boolean; attribute: string }>;
      }>("/admin/api-keys");
      return Object.entries(raw.api_keys).map(([service, info]) => ({
        service,
        configured: info.configured,
        validFrom: null,
        expiresAt: null,
        lastVerified: new Date(),
        status: info.configured ? ("valid" as const) : ("unconfigured" as const),
      }));
    },

    setAPIKey: async (service: string, key: string): Promise<{ configured: boolean; message: string }> => {
      return this.request("/admin/set-api-key", {
        method: "POST",
        body: JSON.stringify({ service, key }),
      });
    },

    getCacheStats: async (): Promise<CacheStats> => {
      const raw = await this.request<{
        hit_rate: number; total_hits: number; total_misses: number; keys_count: number; memory_bytes: number;
      }>("/admin/cache/stats");
      const total = raw.total_hits + raw.total_misses;
      return {
        hitRate: raw.hit_rate,
        missRate: total > 0 ? raw.total_misses / total : 0,
        totalRequests: total,
        cacheSize: raw.memory_bytes,
        evictions: 0,
      };
    },

    getAuditLog: async (limit: number = 100): Promise<AuditEvent[]> => {
      const raw = await this.request<{ items: Array<{
        id: string; created_at: string; actor_id: string | null;
        event_type: string; entity_type: string; entity_id: string; details_json: Record<string, unknown>;
      }>; total: number }>(`/admin/audit?limit=${limit}`);
      return raw.items.map((e) => ({
        id: e.id,
        timestamp: new Date(e.created_at),
        userId: e.actor_id ?? "system",
        action: e.event_type,
        resource: e.entity_type,
        resourceId: e.entity_id,
        changes: e.details_json,
        ipAddress: "",
      }));
    },

    clearCache: async (): Promise<{ cleared: number }> => {
      return this.request("/admin/cache/clear", {
        method: "POST",
      });
    },

    verifyAPIKey: async (service: string): Promise<{ valid: boolean }> => {
      return this.request("/admin/verify-api-key", {
        method: "POST",
        body: JSON.stringify({ service }),
      });
    },
  };
}

export const apiClient = new APIClient();
