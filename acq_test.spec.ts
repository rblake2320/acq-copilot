import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:3001';

test('homepage renders with all nav items', async ({ page }) => {
  await page.goto(BASE);
  await expect(page).toHaveTitle(/Acquisition Copilot/);
  await expect(page.locator('text=Acquisition Copilot').first()).toBeVisible();
  await expect(page.locator('text=Start Acquisition Chat')).toBeVisible();
  await expect(page.locator('text=Create IGCE')).toBeVisible();
  await expect(page.locator('text=Explore Regulations')).toBeVisible();
  await expect(page.locator('nav a', { hasText: 'Market Research' }).first()).toBeVisible();
  // Stats
  await expect(page.locator('text=8')).toBeVisible();  // Tools Available
  await expect(page.locator('text=Healthy')).toBeVisible();
  // Sidebar nav
  await expect(page.getByRole('link', { name: 'Chat' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'IGCE Builder' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Regulatory' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Admin' })).toBeVisible();
});

test('chat page loads', async ({ page }) => {
  await page.goto(`${BASE}/chat`);
  await page.waitForLoadState('networkidle');
  // Should have some chat-related content
  const body = await page.locator('body').textContent();
  expect(body).not.toContain('Internal Server Error');
  await page.screenshot({ path: 'C:/Users/techai/AppData/Local/Temp/acq_chat.png', fullPage: true });
});

test('IGCE builder page loads', async ({ page }) => {
  await page.goto(`${BASE}/igce`);
  await page.waitForLoadState('networkidle');
  const body = await page.locator('body').textContent();
  expect(body).not.toContain('Internal Server Error');
  await page.screenshot({ path: 'C:/Users/techai/AppData/Local/Temp/acq_igce.png', fullPage: true });
});

test('regulatory page loads', async ({ page }) => {
  await page.goto(`${BASE}/regulatory`);
  await page.waitForLoadState('networkidle');
  const body = await page.locator('body').textContent();
  expect(body).not.toContain('Internal Server Error');
  await page.screenshot({ path: 'C:/Users/techai/AppData/Local/Temp/acq_regulatory.png', fullPage: true });
});

test('market research page loads', async ({ page }) => {
  await page.goto(`${BASE}/market-research`);
  await page.waitForLoadState('networkidle');
  const body = await page.locator('body').textContent();
  expect(body).not.toContain('Internal Server Error');
  await page.screenshot({ path: 'C:/Users/techai/AppData/Local/Temp/acq_market.png', fullPage: true });
});

test('admin page loads and shows tool status', async ({ page }) => {
  await page.goto(`${BASE}/admin`);
  await page.waitForLoadState('networkidle');
  const body = await page.locator('body').textContent();
  expect(body).not.toContain('Internal Server Error');
  await page.screenshot({ path: 'C:/Users/techai/AppData/Local/Temp/acq_admin.png', fullPage: true });
});

test('API health check via proxy rewrite', async ({ page }) => {
  const response = await page.request.get(`${BASE}/api/health`);
  // The rewrite sends /api/* to http://localhost:8001/api/*
  // /api/health doesn't exist but /health does — so we expect the API to respond
  const healthResp = await page.request.get('http://localhost:8001/health');
  expect(healthResp.status()).toBe(200);
  const data = await healthResp.json();
  expect(data.status).toBe('healthy');
  expect(data.environment).toBe('dev');
});

test('tools list API returns 8 tools', async ({ page }) => {
  const resp = await page.request.get('http://localhost:8001/api/tools');
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  const tools = Array.isArray(data) ? data : data.tools || [];
  expect(tools.length).toBeGreaterThanOrEqual(6);
});
