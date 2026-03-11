"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RegulatoryResult } from "@/types";
import { formatDate } from "@/lib/format";

export default function RegulatoryPage() {
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["regulatory", query, activeTab],
    queryFn: async () => {
      if (!query.trim()) return [];

      if (activeTab === "fr") {
        return apiClient.regulatory.getFederalRegister(query);
      } else if (activeTab === "ecfr") {
        const titleNum = parseInt(query);
        if (!isNaN(titleNum)) {
          return apiClient.regulatory.getECFR(titleNum);
        }
        return [];
      } else if (activeTab === "regulations-gov") {
        return apiClient.regulatory.getRegulationsGov(query);
      } else {
        return apiClient.regulatory.search(query);
      }
    },
    enabled: query.trim().length > 0,
  });

  const getSourceBadgeColor = (source: string) => {
    switch (source) {
      case "FR":
        return "bg-blue-500/10 text-blue-700 dark:text-blue-400";
      case "eCFR":
        return "bg-purple-500/10 text-purple-700 dark:text-purple-400";
      case "Regulations.gov":
        return "bg-green-500/10 text-green-700 dark:text-green-400";
      default:
        return "bg-muted text-muted-foreground dark:bg-muted dark:text-muted-foreground";
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground dark:text-foreground">
          Regulatory Tracker
        </h1>
        <p className="mt-2 text-muted-foreground dark:text-muted-foreground">
          Search Federal Register, eCFR, and Regulations.gov for compliance requirements and
          regulatory guidance
        </p>
      </div>

      {/* Search */}
      <Card className="dark:bg-card">
        <CardHeader>
          <CardTitle className="dark:text-foreground">Search Regulations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="e.g., federal acquisition, contracting, compliance..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 dark:border-border"
            />
            <Button className="gap-2 dark:hover:bg-primary/80">
              <Search className="h-4 w-4" />
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      {query.trim() && (
        <Tabs defaultValue={activeTab} onChange={setActiveTab} className="space-y-4">
          <TabsList className="dark:bg-muted">
            <TabsTrigger value="all">All Results</TabsTrigger>
            <TabsTrigger value="fr">Federal Register</TabsTrigger>
            <TabsTrigger value="ecfr">eCFR</TabsTrigger>
            <TabsTrigger value="regulations-gov">Regulations.gov</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="space-y-3">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : results.length === 0 ? (
              <Card className="dark:bg-card">
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground dark:text-muted-foreground">
                    No regulations found for your search
                  </p>
                </CardContent>
              </Card>
            ) : (
              results.map((result: RegulatoryResult, idx) => (
                <Card key={idx} className="dark:bg-card hover:shadow-md transition-all">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="mb-2 flex items-center gap-2">
                          <CardTitle className="line-clamp-2 dark:text-foreground">
                            {result.title}
                          </CardTitle>
                          <Badge
                            variant="secondary"
                            className={getSourceBadgeColor(result.source)}
                          >
                            {result.source}
                          </Badge>
                        </div>
                        {result.regulation && (
                          <p className="text-xs font-mono text-muted-foreground dark:text-muted-foreground">
                            {result.regulation}
                          </p>
                        )}
                      </div>
                      <a
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 text-primary hover:text-primary/80 dark:text-primary"
                      >
                        <ExternalLink className="h-5 w-5" />
                      </a>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm text-foreground dark:text-foreground">
                      {result.summary}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground dark:text-muted-foreground">
                      <span>Effective: {formatDate(new Date(result.effectiveDate))}</span>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </TabsContent>
        </Tabs>
      )}

      {/* Info Card */}
      {!query.trim() && (
        <Card className="border-dashed bg-muted/30 dark:bg-muted/10">
          <CardHeader>
            <CardTitle className="dark:text-foreground">Getting Started</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground dark:text-muted-foreground">
            <p>
              Search across federal regulatory databases to find relevant compliance requirements:
            </p>
            <ul className="list-inside list-disc space-y-1 pl-2">
              <li>
                <strong>Federal Register:</strong> Recent regulatory notices, proposed rules, and
                final rules
              </li>
              <li>
                <strong>eCFR:</strong> Electronic Code of Federal Regulations (searchable by title
                number)
              </li>
              <li>
                <strong>Regulations.gov:</strong> Public comments and regulatory docket documents
              </li>
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
