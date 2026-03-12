"use client";

import React, { useState } from "react";
import { Message, Citation } from "@/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, ExternalLink, ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";

/** Escape HTML special chars in a plain text string. */
function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Apply inline markdown (bold, italic, code) to an already-escaped string. */
function inlineMarkdown(s: string): string {
  return s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, '<code class="bg-black/10 dark:bg-white/10 rounded px-1 font-mono text-xs">$1</code>');
}

/** Minimal line-by-line markdown → HTML converter (no external deps). */
function renderMarkdown(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];

    // --- Table (header row + separator row) ---
    if (/^\|.+\|/.test(raw) && i + 1 < lines.length && /^\|[\s\-:|]+\|/.test(lines[i + 1])) {
      const headers = raw.split("|").slice(1, -1).map((h) => `<th class="border border-border/40 px-2 py-1 bg-muted/50 text-left font-semibold">${inlineMarkdown(esc(h.trim()))}</th>`).join("");
      const rows: string[] = [];
      i += 2;
      while (i < lines.length && /^\|.+\|/.test(lines[i])) {
        const cells = lines[i].split("|").slice(1, -1).map((c) => `<td class="border border-border/40 px-2 py-1">${inlineMarkdown(esc(c.trim()))}</td>`).join("");
        rows.push(`<tr>${cells}</tr>`);
        i++;
      }
      out.push(`<div class="overflow-x-auto my-2"><table class="text-xs w-full border-collapse"><thead><tr>${headers}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`);
      continue;
    }

    // --- Headings ---
    const h3 = raw.match(/^### (.+)/);
    if (h3) { out.push(`<h3 class="text-sm font-semibold mt-3 mb-1">${inlineMarkdown(esc(h3[1]))}</h3>`); i++; continue; }
    const h2 = raw.match(/^## (.+)/);
    if (h2) { out.push(`<h2 class="text-base font-semibold mt-4 mb-1">${inlineMarkdown(esc(h2[1]))}</h2>`); i++; continue; }
    const h1 = raw.match(/^# (.+)/);
    if (h1) { out.push(`<h1 class="text-lg font-bold mt-4 mb-2">${inlineMarkdown(esc(h1[1]))}</h1>`); i++; continue; }

    // --- Horizontal rule ---
    if (/^---+$/.test(raw.trim())) { out.push('<hr class="my-2 border-border/40" />'); i++; continue; }

    // --- Unordered list ---
    if (/^[-*•] /.test(raw)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*•] /.test(lines[i])) {
        items.push(`<li class="ml-1">${inlineMarkdown(esc(lines[i].replace(/^[-*•] /, "")))}</li>`);
        i++;
      }
      out.push(`<ul class="list-disc pl-5 my-1 space-y-0.5">${items.join("")}</ul>`);
      continue;
    }

    // --- Ordered list ---
    if (/^\d+\. /.test(raw)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(`<li class="ml-1">${inlineMarkdown(esc(lines[i].replace(/^\d+\. /, "")))}</li>`);
        i++;
      }
      out.push(`<ol class="list-decimal pl-5 my-1 space-y-0.5">${items.join("")}</ol>`);
      continue;
    }

    // --- Blank line (paragraph break) ---
    if (raw.trim() === "") { out.push('<div class="mb-2"></div>'); i++; continue; }

    // --- Regular line ---
    out.push(`<p class="mb-1">${inlineMarkdown(esc(raw))}</p>`);
    i++;
  }

  return out.join("\n");
}

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
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        ) : (
          <div
            className="text-sm leading-relaxed max-w-none"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
          />
        )}

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
            {message.toolRuns.map((run, idx) => (
              <Badge key={run.id ?? String(idx)} variant="secondary" className="text-xs">
                {run.name ?? run.toolName}
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
