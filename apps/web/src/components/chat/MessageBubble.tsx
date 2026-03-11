"use client";

import React, { useState } from "react";
import { Message, Citation } from "@/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, ExternalLink, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [expandedCitations, setExpandedCitations] = useState(false);
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [saving, setSaving] = useState(false);
  const isUser = message.role === "user";

  const handleRate = async (value: 1 | -1) => {
    if (saving || rating === value) return;
    setSaving(true);
    try {
      await apiClient.chat.rateMessage(message.id, value);
      setRating(value);
    } catch {
      // silently ignore — feedback is best-effort
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-2xl rounded-lg p-4",
          isUser
            ? "bg-primary text-primary-foreground dark:bg-primary dark:text-primary-foreground"
            : "bg-muted text-foreground dark:bg-muted dark:text-foreground"
        )}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </p>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && !isUser && (
          <div className="mt-4 space-y-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpandedCitations(!expandedCitations)}
              className="gap-2 px-0 text-xs text-muted-foreground hover:text-foreground dark:hover:text-foreground"
            >
              {expandedCitations ? <ChevronUp /> : <ChevronDown />}
              {message.citations.length} citation{message.citations.length !== 1 ? "s" : ""}
            </Button>

            {expandedCitations && (
              <div className="space-y-2">
                {message.citations.map((citation, idx) => (
                  <div
                    key={idx}
                    className="rounded bg-background/50 p-2 text-xs dark:bg-background/30"
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1">
                        <p className="font-semibold text-foreground dark:text-foreground">
                          {citation.source}
                        </p>
                        <p className="text-muted-foreground dark:text-muted-foreground">
                          {citation.snippet}
                        </p>
                      </div>
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 text-primary hover:underline dark:text-primary"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tool Runs */}
        {message.toolRuns && message.toolRuns.length > 0 && !isUser && (
          <div className="mt-3 space-y-1">
            {message.toolRuns.map((toolRunId) => (
              <Badge key={toolRunId} variant="secondary" className="text-xs">
                {toolRunId}
              </Badge>
            ))}
          </div>
        )}

        {/* Feedback buttons — only on assistant messages */}
        {!isUser && (
          <div className="mt-3 flex items-center gap-1 border-t border-border/30 pt-2">
            <span className="text-xs text-muted-foreground mr-1">Rate this response:</span>
            <button
              onClick={() => handleRate(1)}
              disabled={saving}
              title="Thumbs up — good response"
              className={cn(
                "rounded p-1 transition-colors",
                rating === 1
                  ? "text-green-500"
                  : "text-muted-foreground hover:text-green-500"
              )}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => handleRate(-1)}
              disabled={saving}
              title="Thumbs down — needs improvement"
              className={cn(
                "rounded p-1 transition-colors",
                rating === -1
                  ? "text-red-500"
                  : "text-muted-foreground hover:text-red-500"
              )}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
            {rating !== null && (
              <span className="text-xs text-muted-foreground ml-1">
                {rating === 1 ? "Marked as helpful" : "Marked for improvement"}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
