"use client";

import React, { useState } from "react";
import { IGCEOutput } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Download, Edit2, Eye, EyeOff } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { formatCurrency } from "@/lib/format";

interface IGCEResultsProps {
  result: IGCEOutput;
}

export function IGCEResults({ result }: IGCEResultsProps) {
  const [showDetails, setShowDetails] = useState(false);

  const handleExport = async () => {
    try {
      const response = await fetch("/api/igce/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(result),
      });
      if (!response.ok) throw new Error(`Export failed: ${response.statusText}`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `IGCE_${result.input.projectName}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Labor Total
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {formatCurrency(result.laborTotal)}
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Travel Total
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {formatCurrency(result.travelTotal)}
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Contingency
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {formatCurrency(result.contingencyTotal)}
            </div>
          </CardContent>
        </Card>

        <Card className="dark:bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground dark:text-muted-foreground">
              Profit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground dark:text-foreground">
              {formatCurrency(result.profitTotal)}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-primary/10 dark:bg-primary/10">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-primary dark:text-primary">
              Total Estimate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary dark:text-primary">
              {formatCurrency(result.finalTotal)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="details">
        <TabsList className="dark:bg-muted">
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="sensitivity">Sensitivity</TabsTrigger>
          <TabsTrigger value="formulas">Formulas</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        {/* Details Tab */}
        <TabsContent value="details" className="space-y-4">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Project Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <h3 className="font-semibold text-foreground dark:text-foreground">
                  {result.input.projectName}
                </h3>
                <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                  {result.input.projectDescription}
                </p>
              </div>
              <div className="text-xs text-muted-foreground dark:text-muted-foreground">
                {result.input.performancePeriod.startDate.toString().split("T")[0]} to{" "}
                {result.input.performancePeriod.endDate.toString().split("T")[0]}
              </div>
            </CardContent>
          </Card>

          {/* Labor Summary Table */}
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Labor Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border dark:border-border">
                      <th className="px-4 py-2 text-left text-muted-foreground dark:text-muted-foreground">
                        Year
                      </th>
                      <th className="px-4 py-2 text-right text-muted-foreground dark:text-muted-foreground">
                        Amount
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.laborByYear).map(([year, amount]) => (
                      <tr
                        key={year}
                        className="border-b border-border last:border-0 dark:border-border"
                      >
                        <td className="px-4 py-2 text-foreground dark:text-foreground">
                          {year}
                        </td>
                        <td className="px-4 py-2 text-right font-medium text-foreground dark:text-foreground">
                          {formatCurrency(amount as number)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sensitivity Tab */}
        <TabsContent value="sensitivity">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Price Sensitivity Analysis</CardTitle>
              <CardDescription>Low, Base, and High estimates</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-lg border border-border bg-red-500/10 p-4 dark:border-border">
                  <h4 className="font-semibold text-red-700 dark:text-red-400">Low Estimate</h4>
                  <p className="mt-2 text-2xl font-bold text-foreground dark:text-foreground">
                    {formatCurrency(result.sensitivity.low)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
                    Conservative assumptions
                  </p>
                </div>

                <div className="rounded-lg border border-border bg-blue-500/10 p-4 dark:border-border">
                  <h4 className="font-semibold text-blue-700 dark:text-blue-400">Base Estimate</h4>
                  <p className="mt-2 text-2xl font-bold text-foreground dark:text-foreground">
                    {formatCurrency(result.sensitivity.base)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
                    Expected value
                  </p>
                </div>

                <div className="rounded-lg border border-border bg-green-500/10 p-4 dark:border-border">
                  <h4 className="font-semibold text-green-700 dark:text-green-400">
                    High Estimate
                  </h4>
                  <p className="mt-2 text-2xl font-bold text-foreground dark:text-foreground">
                    {formatCurrency(result.sensitivity.high)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground dark:text-muted-foreground">
                    Optimistic assumptions
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Formulas Tab */}
        <TabsContent value="formulas">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Cost Calculation Formulas</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(result.formulas).map(([key, formula]) => (
                  <div
                    key={key}
                    className="rounded-lg border border-border bg-muted/50 p-3 dark:border-border dark:bg-muted/20"
                  >
                    <h4 className="text-xs font-semibold uppercase text-muted-foreground dark:text-muted-foreground">
                      {key}
                    </h4>
                    <code className="mt-1 block text-xs text-foreground dark:text-foreground">
                      {formula as string}
                    </code>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sources Tab */}
        <TabsContent value="sources">
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">References & Sources</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {result.citations.map((citation, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-border p-3 dark:border-border"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-foreground dark:text-foreground">
                          {citation.source}
                        </p>
                        <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                          {citation.snippet}
                        </p>
                      </div>
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline dark:text-primary"
                      >
                        Link
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="flex justify-between gap-4">
        <Button variant="outline" onClick={() => setShowDetails(!showDetails)} className="gap-2 dark:border-border">
          {showDetails ? <EyeOff /> : <Eye />}
          {showDetails ? "Hide" : "Show"} Details
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport} className="gap-2 dark:border-border">
            <Download className="h-4 w-4" />
            Export to Excel
          </Button>
          <Button className="gap-2 dark:hover:bg-primary/80">
            <Edit2 className="h-4 w-4" />
            Edit Estimate
          </Button>
        </div>
      </div>
    </div>
  );
}
