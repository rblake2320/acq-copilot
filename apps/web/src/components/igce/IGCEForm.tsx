"use client";

import React, { useState } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2, ChevronRight, ChevronLeft, Loader2, Search, MapPin } from "lucide-react";
import { apiClient } from "@/lib/api";
import { IGCEOutput } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IGCEResults } from "./IGCEResults";

const STEP_FIELDS: Record<number, string[]> = {
  1: ["projectName", "projectDescription", "performancePeriod"],
  2: ["laborCategories"],
  3: ["travelEvents"],
  4: ["assumptions"],
};

const laborCategorySchema = z.object({
  name: z.string().min(1, "Category name required"),
  baseRate: z.number().min(0, "Rate must be positive"),
  escalationRate: z.number().min(0).max(100, "0-100%"),
  lines: z.array(
    z.object({
      year: z.number().min(1, "Year required"),
      hours: z.number().min(1, "Hours required"),
    })
  ),
});

const travelEventSchema = z.object({
  destination: z.string().min(1, "Destination required"),
  purpose: z.string().min(1, "Purpose required"),
  duration: z.number().min(1, "Duration required"),
  frequency: z.number().min(1, "Frequency required"),
  transportationCost: z.number().min(0),
  lodging: z.number().min(0),
  mealsAndIncidentals: z.number().min(0),
});

const igceFormSchema = z.object({
  projectName: z.string().min(1, "Project name required"),
  projectDescription: z.string().min(1, "Description required"),
  performancePeriod: z.object({
    startDate: z.string(),
    endDate: z.string(),
  }),
  laborCategories: z.array(laborCategorySchema).min(1, "At least one labor category required"),
  travelEvents: z.array(travelEventSchema),
  assumptions: z.object({
    laborEscalation: z.number().min(0).max(100),
    travelCostInflation: z.number().min(0).max(100),
    contingency: z.number().min(0).max(100),
    profitMargin: z.number().min(0).max(100),
    notes: z.string().optional(),
  }),
});

type IGCEFormInputs = z.infer<typeof igceFormSchema>;

interface BLSResult {
  soc_code: string;
  title: string;
  mean_hourly: number;
  median_hourly: number;
  mean_annual: number;
  median_annual: number;
}

interface PerDiemResult {
  location: string;
  max_lodging: number;
  meals_incidentals: number;
  total_per_day: number;
  source: string;
}

interface IGCEFormProps {
  onSuccess?: (result: IGCEOutput) => void;
}

export function IGCEForm({ onSuccess }: IGCEFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [result, setResult] = useState<IGCEOutput | null>(null);

  // BLS lookup state: per labor category index
  const [blsPopup, setBlsPopup] = useState<{ idx: number; results: BLSResult[] } | null>(null);
  const [blsLoading, setBlsLoading] = useState<Record<number, boolean>>({});

  // Per diem state: per travel event index
  const [perDiemFeedback, setPerDiemFeedback] = useState<Record<number, PerDiemResult | null>>({});
  const [perDiemLoading, setPerDiemLoading] = useState<Record<number, boolean>>({});

  const { control, handleSubmit, register, trigger, getValues, setValue, formState: { errors } } =
    useForm<IGCEFormInputs>({
      resolver: zodResolver(igceFormSchema),
      defaultValues: {
        projectName: "",
        projectDescription: "",
        performancePeriod: { startDate: "", endDate: "" },
        laborCategories: [{ name: "", baseRate: 0, escalationRate: 2, lines: [] }],
        travelEvents: [],
        assumptions: {
          laborEscalation: 2,
          travelCostInflation: 2,
          contingency: 10,
          profitMargin: 15,
        },
      },
    });

  const { fields: laborFields, append: appendLabor, remove: removeLabor } = useFieldArray({
    control,
    name: "laborCategories",
  });

  const { fields: travelFields, append: appendTravel, remove: removeTravel } = useFieldArray({
    control,
    name: "travelEvents",
  });

  const calculateMutation = useMutation({
    mutationFn: (data: IGCEFormInputs) =>
      apiClient.igce.calculate({
        projectName: data.projectName,
        projectDescription: data.projectDescription,
        performancePeriod: {
          startDate: new Date(data.performancePeriod.startDate),
          endDate: new Date(data.performancePeriod.endDate),
        },
        laborCategories: data.laborCategories.map((lc) => ({
          id: `lc-${Math.random()}`,
          name: lc.name,
          baseRate: lc.baseRate,
          escalationRate: lc.escalationRate,
          lines: lc.lines.map((l, idx) => ({
            id: `line-${idx}`,
            category: lc.name,
            laborCategory: lc.name,
            year: l.year,
            rate: lc.baseRate,
            hours: l.hours,
            subtotal: lc.baseRate * l.hours,
          })),
        })),
        travelEvents: travelFields.map((te, idx) => ({
          ...te,
          id: `travel-${idx}`,
        })),
        assumptions: {
          ...data.assumptions,
          notes: data.assumptions.notes ?? "",
        },
      }),
    onSuccess: (data) => {
      setResult(data);
      setCurrentStep(5);
      onSuccess?.(data);
    },
  });

  const onNextClick = async () => {
    const fieldsToValidate = STEP_FIELDS[currentStep] as Parameters<typeof trigger>[0];
    const valid = await trigger(fieldsToValidate);
    if (valid) setCurrentStep((s) => s + 1);
  };

  const onSubmit = handleSubmit(async (data) => {
    calculateMutation.mutate(data);
  });

  // BLS rate lookup
  const handleBLSLookup = async (idx: number) => {
    const name = getValues(`laborCategories.${idx}.name`);
    if (!name?.trim()) return;
    setBlsLoading((prev) => ({ ...prev, [idx]: true }));
    setBlsPopup(null);
    try {
      const res = await fetch(`/api/igce/bls-lookup?q=${encodeURIComponent(name)}`);
      const data = await res.json();
      setBlsPopup({ idx, results: data.results || [] });
    } catch {
      // ignore
    } finally {
      setBlsLoading((prev) => ({ ...prev, [idx]: false }));
    }
  };

  const applyBLSRate = (idx: number, result: BLSResult) => {
    setValue(`laborCategories.${idx}.baseRate`, result.median_hourly);
    setBlsPopup(null);
  };

  // GSA Per Diem lookup
  const handlePerDiemLookup = async (idx: number) => {
    const destination = getValues(`travelEvents.${idx}.destination`);
    if (!destination?.trim()) return;
    // Parse "City, ST" or "City ST"
    const parts = destination.split(/,\s*|\s+/);
    const state = parts[parts.length - 1]?.trim();
    const city = parts.slice(0, parts.length - 1).join(" ").trim() || destination;
    if (!city || !state || state.length > 3) return;

    setPerDiemLoading((prev) => ({ ...prev, [idx]: true }));
    setPerDiemFeedback((prev) => ({ ...prev, [idx]: null }));
    try {
      const res = await fetch(
        `/api/igce/perdiem-lookup?city=${encodeURIComponent(city)}&state=${encodeURIComponent(state)}`
      );
      const data: PerDiemResult = await res.json();
      // Auto-fill lodging and M&IE
      setValue(`travelEvents.${idx}.lodging`, data.max_lodging);
      setValue(`travelEvents.${idx}.mealsAndIncidentals`, data.meals_incidentals);
      setPerDiemFeedback((prev) => ({ ...prev, [idx]: data }));
    } catch {
      // ignore
    } finally {
      setPerDiemLoading((prev) => ({ ...prev, [idx]: false }));
    }
  };

  if (result) {
    return <IGCEResults result={result} />;
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div className="space-y-4">
        {/* Step Indicator */}
        <div className="flex justify-between">
          {[1, 2, 3, 4].map((step) => (
            <button
              key={step}
              type="button"
              onClick={() => setCurrentStep(step)}
              className={`h-10 w-10 rounded-full font-semibold transition-all ${
                step === currentStep
                  ? "bg-primary text-primary-foreground"
                  : step < currentStep
                  ? "bg-green-500 text-white"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {step}
            </button>
          ))}
        </div>

        {/* Step 1: Project Basics */}
        {currentStep === 1 && (
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Project Basics</CardTitle>
              <CardDescription>Define the project and performance period</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-foreground dark:text-foreground">
                  Project Name
                </label>
                <Input
                  {...register("projectName")}
                  placeholder="e.g., Federal IT Services Modernization"
                  className="dark:border-border"
                />
                {errors.projectName && (
                  <p className="mt-1 text-xs text-red-500">{errors.projectName.message}</p>
                )}
              </div>

              <div>
                <label className="text-sm font-medium text-foreground dark:text-foreground">
                  Project Description
                </label>
                <Input
                  {...register("projectDescription")}
                  placeholder="Describe the scope of work"
                  className="dark:border-border"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Start Date
                  </label>
                  <Controller
                    control={control}
                    name="performancePeriod.startDate"
                    render={({ field }) => (
                      <Input
                        type="date"
                        className="dark:border-border"
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value)}
                        onBlur={field.onBlur}
                        ref={field.ref}
                      />
                    )}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    End Date
                  </label>
                  <Controller
                    control={control}
                    name="performancePeriod.endDate"
                    render={({ field }) => (
                      <Input
                        type="date"
                        className="dark:border-border"
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value)}
                        onBlur={field.onBlur}
                        ref={field.ref}
                      />
                    )}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Labor Categories */}
        {currentStep === 2 && (
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Labor Categories</CardTitle>
              <CardDescription>
                Add job classifications and rates.{" "}
                <span className="text-primary">
                  Type a job title then click Search to pull live BLS wage data.
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {laborFields.map((field, idx) => (
                <div
                  key={field.id}
                  className="space-y-3 rounded-lg border border-border p-4 dark:border-border"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-foreground dark:text-foreground">
                      Category {idx + 1}
                    </h3>
                    {laborFields.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeLabor(idx)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {/* Name + BLS lookup */}
                  <div className="flex gap-2">
                    <Input
                      {...register(`laborCategories.${idx}.name`)}
                      placeholder="e.g., Software Developer, Systems Analyst"
                      className="dark:border-border flex-1"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleBLSLookup(idx)}
                      disabled={blsLoading[idx]}
                      className="shrink-0 gap-1 dark:border-border"
                      title="Look up BLS market wage for this job title"
                    >
                      {blsLoading[idx] ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Search className="h-3.5 w-3.5" />
                      )}
                      BLS Rate
                    </Button>
                  </div>

                  {/* BLS results popup */}
                  {blsPopup?.idx === idx && blsPopup.results.length > 0 && (
                    <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
                      <p className="text-xs font-semibold text-primary">
                        BLS OEWS May 2023 — select to apply median hourly rate:
                      </p>
                      {blsPopup.results.map((r) => (
                        <button
                          key={r.soc_code}
                          type="button"
                          onClick={() => applyBLSRate(idx, r)}
                          className="w-full text-left rounded border border-border p-2 hover:bg-primary/10 transition-colors text-xs"
                        >
                          <span className="font-medium text-foreground">{r.title}</span>
                          <span className="ml-2 text-muted-foreground">
                            Median: ${r.median_hourly}/hr · Mean: ${r.mean_hourly}/hr
                          </span>
                          <Badge variant="secondary" className="ml-2 text-xs">
                            {r.soc_code}
                          </Badge>
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => setBlsPopup(null)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                  {blsPopup?.idx === idx && blsPopup.results.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      No BLS matches found. Try a broader job title (e.g., "Software", "Analyst").
                    </p>
                  )}

                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <label className="text-xs text-muted-foreground">Base Hourly Rate ($)</label>
                      <Input
                        type="number"
                        step="0.01"
                        {...register(`laborCategories.${idx}.baseRate`, { valueAsNumber: true })}
                        placeholder="Hourly rate"
                        className="dark:border-border"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted-foreground">Annual Escalation (%)</label>
                      <Input
                        type="number"
                        step="0.1"
                        {...register(`laborCategories.${idx}.escalationRate`, { valueAsNumber: true })}
                        placeholder="e.g., 2.5"
                        className="dark:border-border"
                      />
                    </div>
                  </div>
                </div>
              ))}

              <Button
                type="button"
                variant="outline"
                onClick={() => appendLabor({ name: "", baseRate: 0, escalationRate: 2, lines: [] })}
                className="w-full gap-2 dark:border-border"
              >
                <Plus className="h-4 w-4" />
                Add Category
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Travel Events */}
        {currentStep === 3 && (
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Travel Events</CardTitle>
              <CardDescription>
                Define travel requirements.{" "}
                <span className="text-primary">
                  Enter a destination as "City, ST" then click Per Diem to auto-fill GSA rates.
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {travelFields.map((field, idx) => (
                <div
                  key={field.id}
                  className="space-y-3 rounded-lg border border-border p-4 dark:border-border"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-foreground dark:text-foreground">
                      Travel Event {idx + 1}
                    </h3>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => removeTravel(idx)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Destination + Per Diem lookup */}
                  <div className="flex gap-2">
                    <Input
                      {...register(`travelEvents.${idx}.destination`)}
                      placeholder='e.g., Washington, DC'
                      className="dark:border-border flex-1"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handlePerDiemLookup(idx)}
                      disabled={perDiemLoading[idx]}
                      className="shrink-0 gap-1 dark:border-border"
                      title="Fetch GSA FY2025 per diem rates for this destination"
                    >
                      {perDiemLoading[idx] ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <MapPin className="h-3.5 w-3.5" />
                      )}
                      Per Diem
                    </Button>
                  </div>

                  {/* Per diem feedback */}
                  {perDiemFeedback[idx] && (
                    <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-2 text-xs">
                      <span className="font-medium text-green-600 dark:text-green-400">
                        GSA FY2025 — {perDiemFeedback[idx]!.location}:
                      </span>{" "}
                      Lodging ${perDiemFeedback[idx]!.max_lodging}/night · M&IE $
                      {perDiemFeedback[idx]!.meals_incidentals}/day · Total $
                      {perDiemFeedback[idx]!.total_per_day}/day
                    </div>
                  )}

                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      {...register(`travelEvents.${idx}.purpose`)}
                      placeholder="Purpose (e.g., Site visit)"
                      className="dark:border-border"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        type="number"
                        {...register(`travelEvents.${idx}.duration`, { valueAsNumber: true })}
                        placeholder="Days/trip"
                        className="dark:border-border"
                      />
                      <Input
                        type="number"
                        {...register(`travelEvents.${idx}.frequency`, { valueAsNumber: true })}
                        placeholder="Trips/yr"
                        className="dark:border-border"
                      />
                    </div>
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.transportationCost`, { valueAsNumber: true })}
                      placeholder="Transportation ($)"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      step="0.01"
                      {...register(`travelEvents.${idx}.lodging`, { valueAsNumber: true })}
                      placeholder="Lodging ($/night)"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      step="0.01"
                      {...register(`travelEvents.${idx}.mealsAndIncidentals`, { valueAsNumber: true })}
                      placeholder="M&IE ($/day)"
                      className="dark:border-border"
                    />
                  </div>
                </div>
              ))}

              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  appendTravel({
                    destination: "",
                    purpose: "",
                    duration: 1,
                    frequency: 1,
                    transportationCost: 500,
                    lodging: 0,
                    mealsAndIncidentals: 0,
                  })
                }
                className="w-full gap-2 dark:border-border"
              >
                <Plus className="h-4 w-4" />
                Add Travel Event
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 4: Assumptions */}
        {currentStep === 4 && (
          <Card className="dark:bg-card">
            <CardHeader>
              <CardTitle className="dark:text-foreground">Assumptions & Adjustments</CardTitle>
              <CardDescription>Set escalation, contingency, and profit factors</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Labor Escalation (%)
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    {...register("assumptions.laborEscalation", { valueAsNumber: true })}
                    className="dark:border-border"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">Typical: 2–4% per FAR 36.203</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Travel Inflation (%)
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    {...register("assumptions.travelCostInflation", { valueAsNumber: true })}
                    className="dark:border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Contingency (%)
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    {...register("assumptions.contingency", { valueAsNumber: true })}
                    className="dark:border-border"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">Typical: 10–15%</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Profit Margin (%)
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    {...register("assumptions.profitMargin", { valueAsNumber: true })}
                    className="dark:border-border"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    FAR 15.404-4: consider complexity, risk, capital investment
                  </p>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-foreground dark:text-foreground">
                  Notes / Methodology
                </label>
                <Input
                  {...register("assumptions.notes")}
                  placeholder="e.g., Rates sourced from BLS OEWS May 2023, validated against GSA CALC+"
                  className="dark:border-border"
                />
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between gap-4">
        <Button
          type="button"
          variant="outline"
          disabled={currentStep === 1}
          onClick={() => setCurrentStep(currentStep - 1)}
          className="gap-2 dark:border-border"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>

        {currentStep < 4 ? (
          <Button type="button" onClick={onNextClick} className="gap-2">
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="submit" disabled={calculateMutation.isPending} className="gap-2">
            {calculateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>Calculate IGCE</>
            )}
          </Button>
        )}
      </div>
    </form>
  );
}
