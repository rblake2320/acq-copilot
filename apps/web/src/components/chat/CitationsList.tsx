"use client";

import React, { useState } from "react";
import { Citation } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalLink, ChevronUp, ChevronDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface CitationsListProps {
  citations?: Citation[] | null;
}

export function CitationsList({ citations }: CitationsListProps) {
  const [expanded, setExpanded] = useState(false);

  const items = citations ?? [];

  if (items.length === 0) return null;

  return (
    <div className="border-t border-border bg-muted/30 p-6 dark:border-border dark:bg-muted/10">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between"
      >
        <h3 className="font-semibold text-foreground dark:text-foreground">
          Sources & Citations ({items.length})
        </h3>
        {expanded ? <ChevronUp /> : <ChevronDown />}
      </button>

      {expanded && (
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {items.map((citation, idx) => {
            const displayTitle = citation.title ?? citation.source ?? citation.url;
            const retrievedAt = citation.retrieved_at
              ? new Date(citation.retrieved_at)
              : citation.timestamp instanceof Date
                ? citation.timestamp
                : null;

            return (
              <Card key={citation.id ?? idx} className="dark:bg-card/50">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="line-clamp-2 text-sm dark:text-foreground">
                      {displayTitle}
                    </CardTitle>
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 text-primary hover:text-primary/80 dark:text-primary"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                  {retrievedAt && (
                    <CardDescription className="text-xs">
                      Retrieved{" "}
                      {formatDistanceToNow(retrievedAt, { addSuffix: true })}
                    </CardDescription>
                  )}
                </CardHeader>
                {(citation.snippet || citation.relevance != null) && (
                  <CardContent className="space-y-3">
                    {citation.snippet && (
                      <p className="line-clamp-3 text-sm text-muted-foreground dark:text-muted-foreground">
                        {citation.snippet}
                      </p>
                    )}
                    <div className="flex items-center justify-end">
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-0 text-xs text-primary underline-offset-4 hover:underline dark:text-primary"
                      >
                        Full article
                      </a>
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
