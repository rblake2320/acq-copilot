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
  AuthResponse,
  UserInfo,
} from "@/types";

const API_BASE = "/api";

/** Read the stored JWT token without importing the full store (avoids circular deps). */
function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("acq_token");
}

class APIClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const token = getStoredToken();
    const authHeader: Record<string, string> = token
      ? { Authorization: `Bearer ${token}` }
      : {};

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeader,
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        error.detail || error.message || `API request failed: ${response.statusText}`
      );
    }

    return response.json();
  }

  auth = {
    login: async (username: string, password: string): Promise<AuthResponse> => {
      // OAuth2 password flow requires form-encoded body
      const form = new URLSearchParams();
      form.append("username", username);
      form.append("password", password);

      const response = await fetch(`${API_BASE}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form.toString(),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Login failed");
      }

      return response.json() as Promise<AuthResponse>;
    },

    register: async (
      username: string,
      email: string,
      password: string
    ): Promise<UserInfo> => {
      return this.request<UserInfo>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      });
    },

    me: async (token: string): Promise<UserInfo> => {
      const response = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch user info");
      }

      return response.json() as Promise<UserInfo>;
    },
  };

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

    rateMessage: async (messageId: string, rating: 1 | -1): Promise<void> => {
      return this.request(`/chat/messages/${messageId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ rating }),
      });
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
      const raw = await this.request<Record<string, unknown>>("/regulatory/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      // API returns { query, federal_register: {documents:[...]}, ecfr: {...}, regulations_gov: {...} }
      // Normalize into a flat array for the UI
      if (Array.isArray(raw)) return raw as RegulatoryResult[];
      const results: RegulatoryResult[] = [];
      const fr = (raw?.federal_register as Record<string, unknown>)?.documents;
      if (Array.isArray(fr)) {
        fr.forEach((d: Record<string, unknown>) => results.push({
          title: String(d.title || ""),
          summary: String(d.abstract || d.summary || ""),
          url: String(d.html_url || d.url || ""),
          source: "FR",
          regulation: String(d.document_number || ""),
          effectiveDate: String(d.publication_date || d.effective_on || new Date().toISOString()),
        }));
      }
      const ecfr = raw?.ecfr as Record<string, unknown>;
      if (ecfr && !ecfr.error) {
        const sections = Array.isArray(ecfr.sections) ? ecfr.sections as Record<string, unknown>[] : (ecfr.title ? [ecfr] : []);
        sections.forEach((s) => results.push({
          title: String(s.label || s.title || "eCFR Section"),
          summary: String(s.subject_text || s.text || ""),
          url: `https://www.ecfr.gov/`,
          source: "eCFR",
          regulation: String(s.identifier || ""),
          effectiveDate: new Date().toISOString(),
        }));
      }
      const rg = (raw?.regulations_gov as Record<string, unknown>)?.data;
      if (Array.isArray(rg)) {
        rg.forEach((d: Record<string, unknown>) => {
          const attrs = (d.attributes as Record<string, unknown>) || {};
          results.push({
            title: String(attrs.title || ""),
            summary: String(attrs.summary || ""),
            url: `https://www.regulations.gov/document/${d.id}`,
            source: "Regulations.gov",
            regulation: String(d.id || ""),
            effectiveDate: String(attrs.modifyDate || new Date().toISOString()),
          });
        });
      }
      return results;
    },

    getFederalRegister: async (query: string): Promise<RegulatoryResult[]> => {
      const raw = await this.request<Record<string, unknown>>("/regulatory/federal-register", {
        params: { query } as unknown,
      } as RequestInit);
      if (Array.isArray(raw)) return raw as RegulatoryResult[];
      const docs = (raw?.documents as Record<string, unknown>[]) || [];
      return docs.map((d) => ({
        title: String(d.title || ""),
        summary: String(d.abstract || ""),
        url: String(d.html_url || ""),
        source: "FR",
        regulation: String(d.document_number || ""),
        effectiveDate: String(d.publication_date || new Date().toISOString()),
      }));
    },

    getECFR: async (titleNumber: number): Promise<RegulatoryResult[]> => {
      const raw = await this.request<Record<string, unknown>>(
        `/regulatory/ecfr/${titleNumber}`
      );
      if (Array.isArray(raw)) return raw as RegulatoryResult[];
      return raw ? [{
        title: String((raw as Record<string, unknown>).label || `eCFR Title ${titleNumber}`),
        summary: String((raw as Record<string, unknown>).subject_text || ""),
        url: `https://www.ecfr.gov/title-${titleNumber}`,
        source: "eCFR",
        regulation: `Title ${titleNumber}`,
        effectiveDate: new Date().toISOString(),
      }] : [];
    },

    getRegulationsGov: async (
      documentType: string
    ): Promise<RegulatoryResult[]> => {
      const raw = await this.request<Record<string, unknown>>(
        `/regulatory/regulations-gov?type=${documentType}`
      );
      if (Array.isArray(raw)) return raw as RegulatoryResult[];
      const data = (raw?.data as Record<string, unknown>[]) || [];
      return data.map((d) => {
        const attrs = (d.attributes as Record<string, unknown>) || {};
        return {
          title: String(attrs.title || ""),
          summary: String(attrs.summary || ""),
          url: `https://www.regulations.gov/document/${d.id}`,
          source: "Regulations.gov",
          regulation: String(d.id || ""),
          effectiveDate: String(attrs.modifyDate || new Date().toISOString()),
        };
      });
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
      const raw = await this.request<Record<string, unknown>>("/market-research/usa-spending", {
        method: "POST",
        body: JSON.stringify({ query, filters }),
      });
      // API returns { status, output: { awards: [...], total_count, page, limit }, duration_ms, citations }
      if (Array.isArray(raw)) return raw as AwardResult[];
      const output = raw?.output as Record<string, unknown>;
      const awards = output?.awards;
      if (Array.isArray(awards)) {
        return (awards as Record<string, unknown>[]).map((a) => ({
          awardId: String(a.award_id || a.piid || ""),
          vendorName: String(a.recipient_name || ""),
          awardAmount: Number(a.award_amount || 0),
          competitiveRange: true,
          awardDate: String(a.period_start || ""),
          contractType: String(a.award_type || "Contract"),
          naicsCode: String(a.naics_code || ""),
          description: String(a.description || ""),
          agencyName: String(a.agency_name || ""),
          url: String(a.usaspending_url || ""),
        } as AwardResult));
      }
      return [];
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

    getTrainingStats: async (): Promise<{
      total_conversations: number;
      total_messages: number;
      thumbs_up: number;
      thumbs_down: number;
      exportable_conversations: number;
    }> => {
      return this.request("/admin/training-data/stats");
    },

    exportTrainingData: (ratedOnly: boolean = false): string => {
      return `${API_BASE}/admin/training-data/export?rated_only=${ratedOnly}`;
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
