"use client";

import React, { useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Send, Loader2, Eye, EyeOff } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MessageBubble } from "./MessageBubble";
import { ToolTracePanel } from "./ToolTracePanel";
import { CitationsList } from "./CitationsList";

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
      setToolRuns(response.toolRuns);
      response.toolRuns.forEach((run) => addToolRun(run));
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
            <Card className="w-full max-w-2xl">
              <div className="space-y-4 p-8 text-center">
                <h3 className="text-xl font-semibold text-foreground dark:text-foreground">
                  Ask Acquisition Copilot
                </h3>
                <p className="text-muted-foreground dark:text-muted-foreground">
                  Questions about IGCE methodology, federal regulations, market
                  trends, or compliance requirements
                </p>
              </div>
            </Card>
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

      {/* Citations */}
      {messages.some((m) => m.citations && m.citations.length > 0) && (
        <CitationsList
          citations={
            messages.find((m) => m.citations && m.citations.length > 0)
              ?.citations || []
          }
        />
      )}

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
