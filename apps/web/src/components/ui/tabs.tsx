"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsContextType {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const TabsContext = React.createContext<TabsContextType | undefined>(undefined);

function useTabs() {
  const context = React.useContext(TabsContext);
  if (!context) {
    throw new Error("useTabs must be used within Tabs");
  }
  return context;
}

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue: string;
  onValueChange?: (value: string) => void;
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ defaultValue, onValueChange, className, ...props }, ref) => {
    const [activeTab, setActiveTab] = React.useState(defaultValue);

    const handleSetActiveTab = (tab: string) => {
      setActiveTab(tab);
      onValueChange?.(tab);
    };

    return (
      <TabsContext.Provider value={{ activeTab, setActiveTab: handleSetActiveTab }}>
        <div ref={ref} className={cn("w-full", className)} {...props} />
      </TabsContext.Provider>
    );
  }
);
Tabs.displayName = "Tabs";

const TabsList = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "inline-flex h-10 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground dark:bg-muted dark:text-muted-foreground",
      className
    )}
    {...props}
  />
));
TabsList.displayName = "TabsList";

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, ...props }, ref) => {
    const { activeTab, setActiveTab } = useTabs();

    return (
      <button
        ref={ref}
        onClick={() => setActiveTab(value)}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          activeTab === value
            ? "bg-background text-foreground shadow-sm dark:bg-card dark:text-foreground"
            : "text-muted-foreground hover:text-foreground dark:hover:text-foreground",
          className
        )}
        {...props}
      />
    );
  }
);
TabsTrigger.displayName = "TabsTrigger";

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, ...props }, ref) => {
    const { activeTab } = useTabs();

    if (activeTab !== value) return null;

    return (
      <div
        ref={ref}
        className={cn(
          "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          className
        )}
        {...props}
      />
    );
  }
);
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };
