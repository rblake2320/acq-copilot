import { test, expect } from "@playwright/test";
test("planning", async ({ page }) => {
  await page.goto("http://localhost:3001/planning");
  await page.waitForTimeout(1000);
  await page.fill("textarea", "Cloud hosting services for web application");
  await page.click("button:has-text('Generate Strategy')");
  await page.waitForTimeout(6000);
  await page.screenshot({ path: "planning-result.png" });
  const body = await page.textContent("body") || "";
  console.log("Has content:", body.includes("OASIS") || body.includes("threshold") || body.includes("error") || body.includes("vehicle"));
});
