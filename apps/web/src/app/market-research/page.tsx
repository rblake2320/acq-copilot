"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AwardResult } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";

export default function MarketResearchPage() {
  const [query, setQuery] = useState("");
  const [naicsFilter, setNaicsFilter] = useState("");
  const [pscFilter, setPscFilter] = useState("");
  const [agencyFilter, setAgencyFilter] = useState("");

  // Any of keyword, naicsCode, pscCode, or agency is sufficient to trigger a search
  const hasSearchCriteria =
    query.trim().length > 0 ||
    naicsFilter.trim().length > 0 ||
    pscFilter.trim().length > 0 ||
    agencyFilter.trim().length > 0;

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["usa-spending", query, naicsFilter, pscFilter, agencyFilter],
    queryFn: async () => {
      return apiClient.marketResearch.searchUSASpending(query, {
        naicsCode: naicsFilter || undefined,
        pscCode: pscFilter || undefined,
        agency: agencyFilter || undefined,
      });
    },
    enabled: hasSearchCriteria,
  });

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground dark:text-foreground">
          Market Research
        </h1>
        <p className="mt-2 text-muted-foreground dark:text-muted-foreground">
          Analyze federal contract awards from USASpending.gov with NAICS and PSC filtering
        </p>
      </div>

      {/* Search and Filters */}
      <Card className="dark:bg-card">
        <CardHeader>
          <CardTitle className="dark:text-foreground">Search Awards</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="Search by vendor name, contract type, or keywords..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 dark:border-border"
            />
            <Button className="gap-2 dark:hover:bg-primary/80">
              <Search className="h-4 w-4" />
              Search
            </Button>
          </div>

          {/* Filters */}
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="text-sm font-medium text-foreground dark:text-foreground">
                NAICS Code
              </label>
              <Input
                type="text"
                placeholder="e.g., 541511"
                value={naicsFilter}
                onChange={(e) => setNaicsFilter(e.target.value)}
                className="mt-1 dark:border-border"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground dark:text-foreground">
                PSC Code
              </label>
              <Input
                type="text"
                placeholder="e.g., D209"
                value={pscFilter}
                onChange={(e) => setPscFilter(e.target.value)}
                className="mt-1 dark:border-border"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground dark:text-foreground">
                Agency
              </label>
              <Input
                type="text"
                placeholder="e.g., DoD"
                value={agencyFilter}
                onChange={(e) => setAgencyFilter(e.target.value)}
                className="mt-1 dark:border-border"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {hasSearchCriteria && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground dark:text-foreground">
              Results ({results.length})
            </h2>
            {isLoading && <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : results.length === 0 ? (
            <Card className="dark:bg-card">
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground dark:text-muted-foreground">
                  No awards found matching your search criteria
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {results.map((result: AwardResult, idx) => (
                <Card
                  key={idx}
                  className="dark:bg-card hover:shadow-md transition-all"
                >
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <CardTitle className="dark:text-foreground">
                          {result.vendorName}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {result.contractType}
                        </CardDescription>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-foreground dark:text-foreground">
                          {formatCurrency(result.awardAmount)}
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {result.competitiveRange && (
                        <Badge variant="success" className="bg-green-500/10 text-green-700 dark:text-green-400">
                          Competitive
                        </Badge>
                      )}
                      <Badge variant="outline" className="dark:border-border">
                        {result.naicsCode}
                      </Badge>
                    </div>

                    <div className="grid gap-4 text-sm md:grid-cols-2">
                      <div>
                        <h4 className="font-semibold text-muted-foreground dark:text-muted-foreground">
                          Award ID
                        </h4>
                        <p className="font-mono text-foreground dark:text-foreground">
                          {result.awardId}
                        </p>
                      </div>
                      <div>
                        <h4 className="font-semibold text-muted-foreground dark:text-muted-foreground">
                          Award Date
                        </h4>
                        <p className="text-foreground dark:text-foreground">
                          {formatDate(new Date(result.awardDate))}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Info Card */}
      {!hasSearchCriteria && (
        <Card className="border-dashed bg-muted/30 dark:bg-muted/10">
          <CardHeader>
            <CardTitle className="dark:text-foreground">About Market Research</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground dark:text-muted-foreground">
            <p>
              Search federal contract awards to understand market dynamics and competitive
              intelligence:
            </p>
            <ul className="list-inside list-disc space-y-1 pl-2">
              <li>
                <strong>Vendor Analysis:</strong> Find companies competing in your market segment
              </li>
              <li>
                <strong>Award Sizing:</strong> Analyze typical contract values by NAICS/PSC
              </li>
              <li>
                <strong>Agency Trends:</strong> Identify which agencies award contracts in your
                industry
              </li>
              <li>
                <strong>Competitive Intelligence:</strong> Track competitor contract wins and
                pricing
              </li>
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
