// Capture the README screenshots from a running, seeded AccessHub, and check the CSV export.
//
//   docker compose up -d && docker compose exec backend flask seed
//   cd frontend && npm run screenshots
//
// Uses the Chrome (or Edge) already installed on this machine via playwright-core, with a
// fresh temporary profile. Env: APP_URL (default http://localhost:5173), BROWSER_CHANNEL
// (chrome | msedge, default chrome). Writes PNGs to docs/screenshots/.

import { readFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright-core';

const BASE = process.env.APP_URL ?? 'http://localhost:5173';
const CHANNEL = process.env.BROWSER_CHANNEL ?? 'chrome';
const OUT = fileURLToPath(new URL('../../docs/screenshots/', import.meta.url));
const PASSWORD = 'Password@123';
const VIEWPORT = { width: 1440, height: 900 };
const TIMEOUT = 90_000; // the dev server and scrypt sign-in are slow on small Docker VMs

async function newPage(browser) {
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(TIMEOUT);
  return { context, page };
}

async function signIn(browser, email) {
  const { context, page } = await newPage(browser);
  await page.goto(`${BASE}/login`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
  return { context, page };
}

/** GET an API path with the page's own session (token from localStorage). */
async function api(page, path) {
  return page.evaluate(async (p) => {
    const token = window.localStorage.getItem('accesshub.accessToken');
    const response = await fetch(`/api${p}`, { headers: { Authorization: `Bearer ${token}` } });
    return response.json();
  }, path);
}

async function shot(page, name, options = {}) {
  await page.waitForTimeout(600); // let charts and transitions settle
  await page.screenshot({ path: `${OUT}${name}.png`, ...options });
  console.log(`  saved docs/screenshots/${name}.png`);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: CHANNEL, headless: true });
  try {
    console.log('Sign-in page');
    {
      const { context, page } = await newPage(browser);
      await page.goto(`${BASE}/login`);
      await page.getByText('Demo accounts', { exact: true }).waitFor();
      await shot(page, 'login');
      await context.close();
    }

    console.log('Admin: dashboard, workflow builder, approval inbox');
    {
      const { context, page } = await signIn(browser, 'admin@accesshub.dev');
      await page.getByRole('heading', { name: 'Requests by application' }).waitFor();
      await shot(page, 'dashboard', { fullPage: true });

      const apps = await api(page, '/applications?per_page=100');
      const aws = apps.items.find((app) => app.name === 'AWS Console') ?? apps.items[0];
      await page.goto(`${BASE}/admin/applications/${aws.id}`);
      const builder = page.getByRole('list', { name: 'Workflow steps' });
      await builder.waitFor();
      await page
        .getByRole('heading', { name: 'Approval workflow' })
        .evaluate((heading) => heading.closest('section').scrollIntoView({ block: 'start' }));
      await page.mouse.wheel(0, -24); // a little breathing room above the section
      await shot(page, 'workflow-builder');

      // The admin is the escalation target, so their inbox shows overdue/escalated items.
      await page.goto(`${BASE}/approvals`);
      await page.getByRole('table', { name: 'Pending approvals' }).locator('tbody tr').first().waitFor();
      await shot(page, 'inbox');
      await context.close();
    }

    console.log('Employee: new request');
    {
      const { context, page } = await signIn(browser, 'employee@accesshub.dev');
      await page.goto(`${BASE}/requests/new`);
      await page.getByRole('radio', { name: /AWS Console/ }).click();
      await page.getByLabel('Access level').selectOption({ label: 'PowerUser' });
      await page
        .getByLabel('Business justification')
        .fill('Investigating the production incident on the payments service this week.');
      await page.getByRole('list', { name: 'Approval chain' }).waitFor();
      await shot(page, 'new-request');
      await context.close();
    }

    console.log('Auditor: request timeline, audit log, CSV export');
    {
      const { context, page } = await signIn(browser, 'auditor@accesshub.dev');
      const rejected = await api(page, '/requests?status=REJECTED&per_page=100');
      const multiStep =
        rejected.items.find((r) => r.total_steps >= 3 && r.current_step >= 2) ??
        rejected.items.find((r) => r.current_step >= 2) ??
        rejected.items[0];
      await page.goto(`${BASE}/requests/${multiStep.id}`);
      await page.getByRole('list', { name: 'Approval timeline' }).waitFor();
      await shot(page, 'request-timeline');

      await page.goto(`${BASE}/audit`);
      // An automatic escalation: system actor, and the approver and due date visibly change.
      // Wait for the filtered list's API response before expanding a row; otherwise the reload
      // replaces the rows and resets the expanded one.
      const filtered = page.waitForResponse(
        (r) => r.url().includes('/api/audit?') && r.url().includes('action=APPROVAL_ESCALATED') && r.ok(),
      );
      await page.getByLabel('Action').selectOption('APPROVAL_ESCALATED');
      await filtered;
      const entries = page.getByRole('table', { name: 'Audit log entries' });
      await entries.locator('tbody tr').first().getByText('APPROVAL_ESCALATED').waitFor();
      const expand = entries.getByRole('button', { name: /^Show changes for event/ }).first();
      await expand.waitFor();
      await expand.click();
      await page.getByRole('table', { name: 'Changes recorded in this event' }).waitFor();
      await shot(page, 'audit-log');

      // The CSV export button, end to end in a real browser.
      const [download] = await Promise.all([
        page.waitForEvent('download'),
        page.getByRole('button', { name: 'Export CSV' }).click(),
      ]);
      const csv = await readFile(await download.path(), 'utf8');
      const lines = csv.trim().split(/\r?\n/);
      const header = lines[0];
      const rows = lines.slice(1);
      const ok =
        /\.csv$/.test(download.suggestedFilename()) &&
        header.startsWith('id,created_at,actor_id') &&
        rows.length > 0 &&
        rows.every((line) => line.includes('APPROVAL_ESCALATED'));
      console.log(`  CSV export: ${download.suggestedFilename()}, ${rows.length} row(s), filter respected: ${ok}`);
      if (!ok) process.exitCode = 1;
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
