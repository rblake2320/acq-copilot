"use client";

import React, { useState } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2, ChevronRight, ChevronLeft, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { IGCEOutput } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IGCEResults } from "./IGCEResults";

// Fields validated per step — avoids cross-step validation blocking navigation
// (typed as string[] here; cast to the right type at call site)
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

interface IGCEFormProps {
  onSuccess?: (result: IGCEOutput) => void;
}

export function IGCEForm({ onSuccess }: IGCEFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [result, setResult] = useState<IGCEOutput | null>(null);
  const { control, handleSubmit, register, trigger, getValues, formState: { errors } } = useForm<IGCEFormInputs>({
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

  // Imperatively validate only the current step's fields, then advance
  const onNextClick = async () => {
    const fieldsToValidate = STEP_FIELDS[currentStep] as Parameters<typeof trigger>[0];
    const valid = await trigger(fieldsToValidate);
    if (valid) {
      setCurrentStep((s) => s + 1);
    }
  };

  // Only used on final step to submit
  const onSubmit = handleSubmit(async (data) => {
    calculateMutation.mutate(data);
  });

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
                  ? "bg-primary text-primary-foreground dark:bg-primary"
                  : step < currentStep
                  ? "bg-green-500 text-white dark:bg-green-600"
                  : "bg-muted text-muted-foreground dark:bg-muted dark:text-muted-foreground"
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
                  {errors.performancePeriod?.startDate && (
                    <p className="mt-1 text-xs text-red-500">{errors.performancePeriod.startDate.message}</p>
                  )}
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
                  {errors.performancePeriod?.endDate && (
                    <p className="mt-1 text-xs text-red-500">{errors.performancePeriod.endDate.message}</p>
                  )}
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
              <CardDescription>Add job classifications and rates</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {laborFields.map((field, idx) => (
                <div key={field.id} className="space-y-3 rounded-lg border border-border p-4 dark:border-border">
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

                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      {...register(`laborCategories.${idx}.name`)}
                      placeholder="e.g., Senior Engineer"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`laborCategories.${idx}.baseRate`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Base hourly rate"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      step="0.1"
                      {...register(`laborCategories.${idx}.escalationRate`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Escalation %"
                      className="dark:border-border"
                    />
                  </div>
                </div>
              ))}

              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  appendLabor({
                    name: "",
                    baseRate: 0,
                    escalationRate: 2,
                    lines: [],
                  })
                }
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
              <CardDescription>Define travel requirements and costs</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {travelFields.map((field, idx) => (
                <div key={field.id} className="space-y-3 rounded-lg border border-border p-4 dark:border-border">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-foreground dark:text-foreground">
                      Travel {idx + 1}
                    </h3>
                    {travelFields.length > 0 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeTravel(idx)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      {...register(`travelEvents.${idx}.destination`)}
                      placeholder="Destination"
                      className="dark:border-border"
                    />
                    <Input
                      {...register(`travelEvents.${idx}.purpose`)}
                      placeholder="Purpose"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.duration`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Duration (days)"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.frequency`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Frequency"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.transportationCost`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Transportation"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.lodging`, {
                        valueAsNumber: true,
                      })}
                      placeholder="Lodging"
                      className="dark:border-border"
                    />
                    <Input
                      type="number"
                      {...register(`travelEvents.${idx}.mealsAndIncidentals`, {
                        valueAsNumber: true,
                      })}
                      placeholder="M&IE"
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
                    transportationCost: 0,
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
                    {...register("assumptions.laborEscalation", {
                      valueAsNumber: true,
                    })}
                    className="dark:border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Travel Inflation (%)
                  </label>
                  <Input
                    type="number"
                    {...register("assumptions.travelCostInflation", {
                      valueAsNumber: true,
                    })}
                    className="dark:border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Contingency (%)
                  </label>
                  <Input
                    type="number"
                    {...register("assumptions.contingency", {
                      valueAsNumber: true,
                    })}
                    className="dark:border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-foreground">
                    Profit Margin (%)
                  </label>
                  <Input
                    type="number"
                    {...register("assumptions.profitMargin", {
                      valueAsNumber: true,
                    })}
                    className="dark:border-border"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-foreground dark:text-foreground">
                  Notes
                </label>
                <Input
                  {...register("assumptions.notes")}
                  placeholder="Any additional assumptions..."
                  className="dark:border-border"
                />
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Navigation Buttons */}
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
          <Button
            type="button"
            onClick={onNextClick}
            className="gap-2 dark:hover:bg-primary/80"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={calculateMutation.isPending}
            className="gap-2 dark:hover:bg-primary/80"
          >
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
