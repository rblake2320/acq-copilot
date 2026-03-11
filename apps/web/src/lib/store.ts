import { create } from "zustand";
import { Message, Conversation, ToolRun } from "@/types";

interface StoreState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  toolRuns: ToolRun[];
  sidebarOpen: boolean;

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
}

export const useStore = create<StoreState>((set) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  toolRuns: [],
  sidebarOpen: true,

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
}));
