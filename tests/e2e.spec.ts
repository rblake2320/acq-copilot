import { test, expect } from '@playwright/test';

test('chat sends real AI response', async ({ page }) => {
  await page.goto('http://localhost:3001/chat');
  await page.waitForTimeout(1000);
  const input = page.locator('textarea, input[type="text"]').first();
  await input.fill('What is FAR Part 15?');
  await input.press('Enter');
  await page.waitForTimeout(12000);
  const body = await page.content();
  // Should NOT see "Processing message..."
  expect(body).not.toContain('Processing message');
  // Should see some real content
  const msgs = page.locator('[class*="message"], [class*="Message"], [class*="chat"], [class*="assistant"]');
  const count = await msgs.count();
  expect(count).toBeGreaterThan(0);
});

test('IGCE calculate returns real totals', async ({ page }) => {
  const res = await page.request.post('http://localhost:8001/api/igce/calculate', {
    data: {
      projectName: 'Test Project',
      projectDescription: 'Test',
      performancePeriod: { startDate: '2025-01-01', endDate: '2025-12-31' },
      laborCategories: [{
        id: 'lc1', name: 'Software Developer', baseRate: 125.0, escalationRate: 3.0,
        lines: [{ id: 'l1', category: 'lc1', laborCategory: 'Software Developer', year: 1, rate: 125.0, hours: 2080, subtotal: 260000 }]
      }],
      travelEvents: [],
      assumptions: { laborEscalation: 3.0, travelCostInflation: 2.0, contingency: 10.0, profitMargin: 15.0, notes: '' }
    }
  });
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.finalTotal).toBeGreaterThan(0);
  expect(data.laborTotal).toBeGreaterThan(0);
  console.log('IGCE final total:', data.finalTotal, 'labor:', data.laborTotal);
});

test('admin shows 7/7 valid keys', async ({ page }) => {
  await page.goto('http://localhost:3001/admin');
  await page.waitForTimeout(6000);
  const content = await page.content();
  expect(content).toContain('7/7');
  const validBadges = await page.locator('text=valid').count();
  expect(validBadges).toBeGreaterThanOrEqual(7);
});

test('market research returns real awards', async ({ page }) => {
  const res = await page.request.post('http://localhost:8001/api/market-research/usa-spending', {
    data: { query: 'software development', page: 1, limit: 5 }
  });
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.output?.awards?.length).toBeGreaterThan(0);
});

test('regulatory search returns real results', async ({ page }) => {
  const res = await page.request.post('http://localhost:8001/api/regulatory/search', {
    data: { query: 'FAR Part 15 source selection', page: 1, limit: 5 }
  });
  expect(res.ok()).toBeTruthy();
  const data = await res.json();
  expect(data.total).toBeGreaterThan(0);
});
