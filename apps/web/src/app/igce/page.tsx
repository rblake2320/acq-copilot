"use client";

import React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { IGCEForm } from "@/components/igce/IGCEForm";

export default function IGCEPage() {
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground dark:text-foreground">
          IGCE Builder
        </h1>
        <p className="mt-2 text-muted-foreground dark:text-muted-foreground">
          Create an Independent Government Cost Estimate with dynamic labor categories,
          travel modeling, and sensitivity analysis
        </p>
      </div>

      {/* Info Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="dark:bg-card/50">
          <CardHeader>
            <CardTitle className="text-lg dark:text-foreground">Labor Categories</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground">
              Define job classifications with hourly rates and annual escalation rates for each
              contract year
            </p>
          </CardContent>
        </Card>

        <Card className="dark:bg-card/50">
          <CardHeader>
            <CardTitle className="text-lg dark:text-foreground">Travel Events</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground">
              Model travel requirements including transportation, lodging, and meals &
              incidentals with frequency adjustments
            </p>
          </CardContent>
        </Card>

        <Card className="dark:bg-card/50">
          <CardHeader>
            <CardTitle className="text-lg dark:text-foreground">Sensitivity Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground">
              Generate low, base, and high estimates with contingency and profit margin
              adjustments
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Form */}
      <Card className="dark:bg-card">
        <CardHeader>
          <CardTitle className="dark:text-foreground">Create New Estimate</CardTitle>
          <CardDescription>
            Step through the IGCE builder to calculate your cost estimate
          </CardDescription>
        </CardHeader>
        <CardContent>
          <IGCEForm />
        </CardContent>
      </Card>
    </div>
  );
}
