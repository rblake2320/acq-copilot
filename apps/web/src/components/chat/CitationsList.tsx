"use client";

import React, { useState } from "react";
import { Citation } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, ChevronUp, ChevronDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface CitationsListProps {
  citations: Citation[];
}

export function CitationsList({ citations }: CitationsListProps) {
  const [expanded, setExpanded] = useState(false);

  if (citations.length === 0) return null;

  return (
    <div className="border-t border-border bg-muted/30 p-6 dark:border-border dark:bg-muted/10">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between"
      >
        <h3 className="font-semibold text-foreground dark:text-foreground">
          Sources & Citations ({citations.length})
        </h3>
        {expanded ? <ChevronUp /> : <ChevronDown />}
      </button>

      {expanded && (
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {citations.map((citation, idx) => (
            <Card key={idx} className="dark:bg-card/50">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle className="line-clamp-2 text-sm dark:text-foreground">
                    {citation.source}
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
                <CardDescription className="text-xs">
                  {formatDistanceToNow(new Date(citation.timestamp), {
                    addSuffix: true,
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="line-clamp-3 text-sm text-muted-foreground dark:text-muted-foreground">
                  {citation.snippet}
                </p>
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs dark:border-border">
                    Relevance: {Math.round(citation.relevance * 100)}%
                  </Badge>
                  <Button
                    variant="link"
                    size="sm"
                    asChild
                    className="p-0 text-xs text-primary dark:text-primary"
                  >
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Full article
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
