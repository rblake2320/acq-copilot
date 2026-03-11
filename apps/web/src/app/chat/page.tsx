"use client";

import React, { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function ChatPage() {
  const { conversations, setConversations, activeConversationId, setActiveConversation } = useStore();

  const { data: loadedConversations = [], isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => apiClient.chat.listConversations(),
  });

  useEffect(() => {
    if (loadedConversations.length > 0) {
      setConversations(
        loadedConversations.map((c: any) => ({
          id: c.id,
          title: c.title,
          createdAt: new Date(c.createdAt),
          updatedAt: new Date(c.updatedAt),
          messageCount: 0,
        }))
      );
      if (!activeConversationId) {
        setActiveConversation(loadedConversations[0].id);
      }
    }
  }, [loadedConversations]);

  const handleNewConversation = async () => {
    try {
      const result = await apiClient.chat.createConversation(
        `Conversation ${new Date().toLocaleString()}`
      );
      setActiveConversation(result.id);
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground dark:text-foreground">
            Acquisition Intelligence Chat
          </h1>
          <p className="text-muted-foreground dark:text-muted-foreground">
            Ask about regulations, cost estimation, market trends, and procurement best practices
          </p>
        </div>
        <Button onClick={handleNewConversation} className="gap-2 dark:hover:bg-primary/80">
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Conversation Selector */}
      {conversations.length > 0 && (
        <div className="flex flex-wrap gap-2 border-b border-border pb-4 dark:border-border">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setActiveConversation(conv.id)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                  activeConversationId === conv.id
                    ? "bg-primary text-primary-foreground dark:bg-primary"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-foreground dark:bg-muted dark:hover:bg-accent/10"
                }`}
              >
                {conv.title}
              </button>
            ))
          )}
        </div>
      )}

      {/* Chat Interface */}
      <div className="flex-1 overflow-hidden rounded-lg border border-border bg-card dark:border-border dark:bg-card">
        <ChatInterface />
      </div>
    </div>
  );
}
