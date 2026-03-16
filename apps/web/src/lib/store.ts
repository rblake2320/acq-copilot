import { create } from "zustand";
import { Message, Conversation, ToolRun, UserInfo } from "@/types";

interface StoreState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  toolRuns: ToolRun[];
  sidebarOpen: boolean;

  // Auth state
  user: UserInfo | null;
  token: string | null;

  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  setActiveConversation: (id: string) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  setToolRuns: (runs: ToolRun[]) => void;
  addToolRun: (run: ToolRun) => void;
  updateToolRun: (id: string, run: Partial<ToolRun>) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  clearConversation: () => void;

  // Auth actions
  setUser: (user: UserInfo, token: string) => void;
  logout: () => void;
}

// Hydrate token from localStorage on init (client-only)
const storedToken =
  typeof window !== "undefined" ? localStorage.getItem("acq_token") : null;

export const useStore = create<StoreState>((set) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  toolRuns: [],
  sidebarOpen: true,

  // Auth initial state
  user: null,
  token: storedToken,

  setConversations: (conversations) => set({ conversations }),

  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),

  setActiveConversation: (id) =>
    set({
      activeConversationId: id,
      messages: [],
      toolRuns: [],
    }),

  setMessages: (messages) => set({ messages }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setToolRuns: (runs) => set({ toolRuns: runs }),

  addToolRun: (run) =>
    set((state) => ({
      toolRuns: [...state.toolRuns, run],
    })),

  updateToolRun: (id, run) =>
    set((state) => ({
      toolRuns: state.toolRuns.map((r) => (r.id === id ? { ...r, ...run } : r)),
    })),

  toggleSidebar: () =>
    set((state) => ({
      sidebarOpen: !state.sidebarOpen,
    })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  clearConversation: () =>
    set({
      messages: [],
      toolRuns: [],
    }),

  setUser: (user, token) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("acq_token", token);
    }
    set({ user, token });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("acq_token");
    }
    set({ user: null, token: null });
  },
}));
