"use client";

import React, { useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Send, Loader2, Eye, EyeOff, Zap } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MessageBubble } from "./MessageBubble";
import { ToolTracePanel } from "./ToolTracePanel";
import { CitationsList } from "./CitationsList";

const SUGGESTED_PROMPTS = [
  "What does FAR Part 15 say about source selection procedures?",
  "Explain the difference between sealed bidding and negotiated acquisition",
  "What are the sole source justification requirements under FAR 6.302?",
  "What BLS wage data exists for Software Developers nationally?",
  "What is the GSA per diem rate for Washington DC?",
  "How do I document IGCE methodology for the contract file per FAR 36.203?",
];

interface ChatFormInputs {
  message: string;
}

export function ChatInterface() {
  const {
    activeConversationId,
    messages,
    addMessage,
    toolRuns,
    setToolRuns,
    addToolRun,
    updateToolRun,
  } = useStore();
  const [showToolTrace, setShowToolTrace] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { register, handleSubmit, reset } = useForm<ChatFormInputs>();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load conversation history
  useQuery({
    queryKey: ["chat-history", activeConversationId],
    queryFn: async () => {
      if (!activeConversationId) return [];
      return apiClient.chat.getHistory(activeConversationId);
    },
    onSuccess: (data) => {
      useStore.setState({ messages: data });
    },
    enabled: !!activeConversationId,
  });

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!activeConversationId) throw new Error("No active conversation");
      return apiClient.chat.send(activeConversationId, content);
    },
    onSuccess: (response) => {
      // Store the assistant reply as a full Message so citations and toolRuns
      // are available to CitationsList and ToolTracePanel from message state.
      const assistantMessage = {
        id: response.messageId,
        conversationId: response.conversationId,
        role: "assistant" as const,
        content: response.content,
        timestamp: new Date(),
        toolRuns: response.toolRuns ?? [],
        citations: response.citations ?? [],
      };
      addMessage(assistantMessage);

      // Also sync the top-level toolRuns slice in the store for the panel.
      const runs = response.toolRuns ?? [];
      setToolRuns(runs);
      runs.forEach((run) => addToolRun(run));
    },
    onError: (error) => {
      console.error("Chat error:", error);
    },
  });

  const onSubmit = handleSubmit(async (data) => {
    if (!data.message.trim() || !activeConversationId) return;

    const userMessage = {
      id: `msg-${Date.now()}`,
      conversationId: activeConversationId,
      role: "user" as const,
      content: data.message,
      timestamp: new Date(),
    };

    addMessage(userMessage);
    reset();

    await sendMutation.mutateAsync(data.message);
  });

  if (!activeConversationId) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <div className="space-y-4 p-8 text-center">
            <h2 className="text-2xl font-bold text-foreground dark:text-foreground">
              Start a Conversation
            </h2>
            <p className="text-muted-foreground dark:text-muted-foreground">
              Select or create a conversation to begin asking questions about
              federal acquisition, regulations, and market analysis.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="w-full max-w-2xl space-y-6">
              <div className="text-center">
                <h3 className="text-xl font-semibold text-foreground dark:text-foreground">
                  Ask Acquisition Copilot
                </h3>
                <p className="mt-1 text-muted-foreground dark:text-muted-foreground">
                  Questions about IGCE methodology, federal regulations, market
                  trends, or compliance requirements
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={sendMutation.isPending}
                    onClick={() => {
                      if (!activeConversationId) return;
                      const userMessage = {
                        id: `msg-${Date.now()}`,
                        conversationId: activeConversationId,
                        role: "user" as const,
                        content: prompt,
                        timestamp: new Date(),
                      };
                      addMessage(userMessage);
                      sendMutation.mutate(prompt);
                    }}
                    className="flex items-start gap-2 rounded-lg border border-border bg-card p-3 text-left text-sm text-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-50 dark:border-border dark:bg-card"
                  >
                    <Zap className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Citations — show citations from the most recent assistant message */}
      {(() => {
        const lastWithCitations = [...messages]
          .reverse()
          .find((m) => m.role === "assistant" && m.citations && m.citations.length > 0);
        return lastWithCitations ? (
          <CitationsList citations={lastWithCitations.citations} />
        ) : null;
      })()}

      {/* Input */}
      <div className="border-t border-border bg-card p-6 dark:border-border dark:bg-card">
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="flex gap-3">
            <Input
              {...register("message", { required: true })}
              placeholder="Ask about IGCE, regulations, market trends..."
              disabled={sendMutation.isPending}
              className="dark:border-border dark:bg-background"
            />
            <Button
              type="submit"
              disabled={sendMutation.isPending}
              className="dark:hover:bg-primary/80"
            >
              {sendMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => setShowToolTrace(!showToolTrace)}
              className="dark:border-border"
            >
              {showToolTrace ? <Eye /> : <EyeOff />}
            </Button>
          </div>
        </form>
      </div>

      {/* Tool Trace Panel */}
      {showToolTrace && <ToolTracePanel toolRuns={toolRuns} />}
    </div>
  );
}
