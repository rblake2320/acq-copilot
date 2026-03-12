"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { useStore } from "@/lib/store";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useStore();

  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        const authResp = await apiClient.auth.login(username, password);
        const userInfo = await apiClient.auth.me(authResp.access_token);
        setUser(userInfo, authResp.access_token);
        router.push("/chat");
      } else {
        // Register then auto-login
        await apiClient.auth.register(username, email, password);
        const authResp = await apiClient.auth.login(username, password);
        const userInfo = await apiClient.auth.me(authResp.access_token);
        setUser(userInfo, authResp.access_token);
        router.push("/chat");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode((m) => (m === "login" ? "register" : "login"));
    setError(null);
    setUsername("");
    setEmail("");
    setPassword("");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        {/* Brand header */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow">
            <span className="text-xl font-bold">AC</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Acq Copilot
          </h1>
          <p className="text-sm text-muted-foreground">
            Federal acquisition intelligence platform
          </p>
        </div>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">
              {mode === "login" ? "Sign in" : "Create account"}
            </CardTitle>
            <CardDescription>
              {mode === "login"
                ? "Enter your credentials to continue."
                : "Fill in the details below to register."}
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-3">
              {/* Username */}
              <div className="space-y-1">
                <label
                  htmlFor="username"
                  className="text-sm font-medium text-foreground"
                >
                  Username
                </label>
                <Input
                  id="username"
                  type="text"
                  autoComplete="username"
                  placeholder="your_username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  disabled={loading}
                />
              </div>

              {/* Email — register only */}
              {mode === "register" && (
                <div className="space-y-1">
                  <label
                    htmlFor="email"
                    className="text-sm font-medium text-foreground"
                  >
                    Email
                  </label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@agency.gov"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
              )}

              {/* Password */}
              <div className="space-y-1">
                <label
                  htmlFor="password"
                  className="text-sm font-medium text-foreground"
                >
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                />
              </div>

              {/* Error message */}
              {error && (
                <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}
            </CardContent>

            <CardFooter className="flex flex-col gap-3 pt-2">
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="h-4 w-4 animate-spin"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    {mode === "login" ? "Signing in..." : "Creating account..."}
                  </span>
                ) : mode === "login" ? (
                  "Sign in"
                ) : (
                  "Create account"
                )}
              </Button>

              <button
                type="button"
                onClick={toggleMode}
                disabled={loading}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
              >
                {mode === "login"
                  ? "Don't have an account? Register"
                  : "Already have an account? Sign in"}
              </button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
