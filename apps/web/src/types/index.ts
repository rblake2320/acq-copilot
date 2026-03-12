export interface Message {
  id: string;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  citations?: Citation[];
  toolRuns?: ToolRun[];
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
}

export interface ToolRun {
  id: string;
  conversationId?: string;
  messageId?: string;
  /** Display name — matches API response field `name` */
  name: string;
  /** @deprecated Use `name`. Kept for store/legacy compatibility. */
  toolName?: string;
  status: "pending" | "running" | "success" | "error" | "timeout";
  input: Record<string, unknown>;
  output: unknown;
  error?: string | null;
  /** Duration in milliseconds — matches API response field `duration_ms` */
  duration_ms: number;
  /** @deprecated Use `duration_ms`. Kept for store/legacy compatibility. */
  executionTime?: number;
  startedAt?: Date;
  completedAt?: Date | null;
}

export interface Citation {
  id?: string;
  /** Display title — matches API response field `title` */
  title: string;
  /** @deprecated Use `title`. Kept for IGCE/legacy compatibility. */
  source?: string;
  url: string;
  /** ISO string — matches API response field `retrieved_at` */
  retrieved_at: string;
  /** @deprecated Use `retrieved_at`. Kept for IGCE/legacy compatibility. */
  timestamp?: Date;
  snippet?: string;
  /** @deprecated Not returned by the new API. */
  relevance?: number;
}

export interface ChatResponse {
  conversationId: string;
  messageId: string;
  content: string;
  citations: Citation[];
  toolRuns: ToolRun[];
}

export interface LaborLine {
  id: string;
  category: string;
  laborCategory: string;
  year: number;
  rate: number;
  hours: number;
  subtotal: number;
}

export interface TravelLine {
  id: string;
  destination: string;
  duration: number;
  frequency: number;
  transportationCost: number;
  lodging: number;
  mealsAndIncidentals: number;
  subtotal: number;
}

export interface LaborCategory {
  id: string;
  name: string;
  baseRate: number;
  escalationRate: number;
  lines: LaborLine[];
}

export interface TravelEvent {
  id: string;
  destination: string;
  purpose: string;
  duration: number;
  frequency: number;
  transportationCost: number;
  lodging: number;
  mealsAndIncidentals: number;
}

export interface IGCEAssumptions {
  laborEscalation: number;
  travelCostInflation: number;
  contingency: number;
  profitMargin: number;
  notes: string;
}

export interface IGCEInput {
  projectName: string;
  projectDescription: string;
  performancePeriod: {
    startDate: Date;
    endDate: Date;
  };
  laborCategories: LaborCategory[];
  travelEvents: TravelEvent[];
  assumptions: IGCEAssumptions;
}

export interface IGCEOutput {
  id: string;
  input: IGCEInput;
  summaryTotal: number;
  laborTotal: number;
  travelTotal: number;
  contingencyTotal: number;
  profitTotal: number;
  finalTotal: number;
  laborByYear: Record<number, number>;
  travelByYear: Record<number, number>;
  sensitivity: {
    low: number;
    base: number;
    high: number;
  };
  formulas: Record<string, string>;
  citations: Citation[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ToolInfo {
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  lastUsed: Date | null;
  usageCount: number;
}

export interface ToolHealthStatus {
  toolName: string;
  status: "healthy" | "degraded" | "error";
  responseTime: number;
  lastChecked: Date;
  errorCount: number;
  successRate: number;
}

export interface AuditEvent {
  id: string;
  timestamp: Date;
  userId: string;
  action: string;
  resource: string;
  resourceId: string;
  changes: Record<string, unknown>;
  ipAddress: string;
}

export interface AwardResult {
  awardId: string;
  vendorName: string;
  awardAmount: number;
  competitiveRange: boolean;
  awardDate: string;
  contractType: string;
  naicsCode: string;
  description?: string;
  agencyName?: string;
  url?: string;
}

export interface RegulatoryResult {
  citationId?: string;
  title: string;
  regulation: string;
  effectiveDate: string;
  source: "FR" | "eCFR" | "Regulations.gov" | string;
  url: string;
  summary: string;
}

export interface CacheStats {
  hitRate: number;
  missRate: number;
  totalRequests: number;
  cacheSize: number;
  evictions: number;
}

export interface APIKeyStatus {
  service: string;
  configured: boolean;
  validFrom: Date | null;
  expiresAt: Date | null;
  lastVerified: Date;
  status: "valid" | "expired" | "invalid" | "unconfigured";
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface UserInfo {
  username: string;
  email: string;
  role: string;
}
