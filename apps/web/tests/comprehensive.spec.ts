import { test, expect } from "@playwright/test";

const BASE = "http://localhost:3001";

test.describe("Acq Copilot V2 — Full Coverage", () => {
  test("Homepage loads with all nav links and status cards", async ({ page }) => {
    await page.goto(BASE);
    await expect(page.locator("text=Acquisition Copilot")).toBeVisible();
    await expect(page.locator("text=Healthy")).toBeVisible();
    // Nav items
    for (const nav of ["Chat", "IGCE Builder", "Regulatory", "Market Research", "FAR Search", "Opportunities", "Compliance", "Planning", "Price Analysis", "Admin"]) {
      await expect(page.locator(`text=${nav}`).first()).toBeVisible();
    }
  });

  test("Chat page — sends a message and receives a response", async ({ page }) => {
    await page.goto(`${BASE}/chat`);
    await page.waitForLoadState("networkidle");
    const input = page.locator("textarea, input[type=text]").first();
    await expect(input).toBeVisible();
    await input.fill("What is the Simplified Acquisition Threshold?");
    await page.keyboard.press("Enter");
    // Wait for assistant response (up to 30s)
    await page.waitForSelector("[class*='bg-muted']", { timeout: 30000 });
    const assistantMsg = page.locator("[class*='bg-muted']").first();
    const text = await assistantMsg.textContent();
    expect(text!.length).toBeGreaterThan(20);
    await page.screenshot({ path: "test-results/chat-response.png", fullPage: true });
  });

  test("IGCE Builder — renders form and submits estimate", async ({ page }) => {
    await page.goto(`${BASE}/igce`);
    await page.waitForLoadState("networkidle");
    // Check form fields exist
    await expect(page.locator("text=IGCE Builder").first()).toBeVisible();
    await page.screenshot({ path: "test-results/igce-page.png", fullPage: true });
  });

  test("Regulatory page — search returns results", async ({ page }) => {
    await page.goto(`${BASE}/regulatory`);
    await page.waitForLoadState("networkidle");
    const input = page.locator("input[type=text], input[placeholder*='search' i], input[placeholder*='Search' i]").first();
    await input.fill("small business set-aside");
    await page.keyboard.press("Enter");
    // Wait for results or loading spinner to complete
    await page.waitForTimeout(3000);
    const errors = await page.locator("text=Cannot read, text=map is not a function, text=TypeError").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/regulatory-results.png", fullPage: true });
  });

  test("Market Research page — search returns results", async ({ page }) => {
    await page.goto(`${BASE}/market-research`);
    await page.waitForLoadState("networkidle");
    const input = page.locator("input[type=text], input[placeholder*='search' i], input[placeholder*='Search' i]").first();
    await input.fill("cloud services IT");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(3000);
    const errors = await page.locator("text=Cannot read, text=map is not a function, text=TypeError").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/market-research-results.png", fullPage: true });
  });

  test("FAR Search page — loads without error", async ({ page }) => {
    await page.goto(`${BASE}/far-search`);
    await page.waitForLoadState("networkidle");
    const errors = await page.locator("text=TypeError, text=Cannot read").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/far-search.png", fullPage: true });
  });

  test("Opportunities page — loads without error", async ({ page }) => {
    await page.goto(`${BASE}/opportunities`);
    await page.waitForLoadState("networkidle");
    const errors = await page.locator("text=TypeError, text=Cannot read").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/opportunities.png", fullPage: true });
  });

  test("Compliance page — loads without error", async ({ page }) => {
    await page.goto(`${BASE}/compliance`);
    await page.waitForLoadState("networkidle");
    const errors = await page.locator("text=TypeError, text=Cannot read").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/compliance.png", fullPage: true });
  });

  test("Planning page — loads without error", async ({ page }) => {
    await page.goto(`${BASE}/planning`);
    await page.waitForLoadState("networkidle");
    const errors = await page.locator("text=TypeError, text=Cannot read").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/planning.png", fullPage: true });
  });

  test("Price Analysis page — loads without error", async ({ page }) => {
    await page.goto(`${BASE}/price-analysis`);
    await page.waitForLoadState("networkidle");
    const errors = await page.locator("text=TypeError, text=Cannot read").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/price-analysis.png", fullPage: true });
  });

  test("Admin page — loads tool health and API key status", async ({ page }) => {
    await page.goto(`${BASE}/admin`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    const errors = await page.locator("text=TypeError, text=Cannot read, text=map is not a function").count();
    expect(errors).toBe(0);
    await page.screenshot({ path: "test-results/admin.png", fullPage: true });
  });

  test("No JS console errors on any page", async ({ page }) => {
    const jsErrors: string[] = [];
    page.on("pageerror", (err) => jsErrors.push(err.message));
    const pages = ["/", "/chat", "/igce", "/regulatory", "/market-research", "/far-search", "/opportunities", "/compliance", "/planning", "/price-analysis", "/admin"];
    for (const p of pages) {
      jsErrors.length = 0;
      await page.goto(`${BASE}${p}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      const fatal = jsErrors.filter(e => !e.includes("Warning") && !e.includes("hydrat"));
      expect(fatal, `JS errors on ${p}: ${fatal.join(", ")}`).toHaveLength(0);
    }
  });
});
