// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
//
// Diagnostic test: how long after clicking "Execute Graph" does the UI receive
// its FIRST NODE_STATUS frame? Run this after `docker compose down && up` to
// reproduce the user-reported "3 minute startup gap."
//
// What it measures:
//   T_click   — when Playwright issues the Execute Graph click
//   T_post    — when POST /api/runs/{ws} returns
//   T_first   — first incoming WS frame after T_click (any type)
//   T_status  — first incoming WS frame whose type is NODE_STATUS or WORKFLOW_STATUS
//
// Run:  cd flowgraph_oss/client && npx playwright test ws-startup-timing
//       (forced single worker so timing is clean)
//
import { expect, test } from '@playwright/test';

const WORKSPACE_ID = '1a9aac5b-db69-42cc-9023-c8569ae75417'; // DEEP_RESEARCH
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:3000';

interface FrameRecord {
  t: number;          // ms since test start
  dir: 'in' | 'out';
  type?: string;
  node_id?: string;
  status?: string;
  raw: string;
}

test.use({ viewport: { width: 1400, height: 900 } });

test('first WS NODE_STATUS arrives within 10s of Execute Graph click', async ({ page, context }) => {
  test.setTimeout(240_000); // 4 min ceiling

  const t0 = Date.now();
  const ms = () => Date.now() - t0;
  const frames: FrameRecord[] = [];

  // Pre-seed localStorage so the canvas auto-loads the DEEP_RESEARCH workspace.
  await context.addInitScript((wsId) => {
    try {
      window.localStorage.setItem('graphmind_current_workspace_id', wsId);
    } catch (_) {}
  }, WORKSPACE_ID);

  // Capture every WebSocket frame on every WS the page opens.
  page.on('websocket', (ws) => {
    const url = ws.url();
    console.log(`[${ms()}ms] WS opened: ${url}`);
    ws.on('framereceived', ({ payload }) => {
      const text = typeof payload === 'string' ? payload : payload.toString();
      let parsed: any = {};
      try { parsed = JSON.parse(text); } catch (_) {}
      frames.push({
        t: ms(),
        dir: 'in',
        type: parsed.type,
        node_id: parsed.node_id,
        status: parsed.status,
        raw: text.slice(0, 200),
      });
    });
    ws.on('framesent', ({ payload }) => {
      const text = typeof payload === 'string' ? payload : payload.toString();
      frames.push({ t: ms(), dir: 'out', raw: text.slice(0, 200) });
    });
    ws.on('close', () => console.log(`[${ms()}ms] WS closed: ${url}`));
  });

  // Capture POST /api/runs timing.
  let tPostReturn: number | null = null;
  page.on('response', async (resp) => {
    const url = resp.url();
    if (url.includes('/api/runs/') && resp.request().method() === 'POST') {
      tPostReturn = ms();
      console.log(`[${tPostReturn}ms] POST /api/runs returned ${resp.status()}`);
    }
  });

  // Navigate.
  console.log(`[${ms()}ms] navigating to ${FRONTEND}`);
  await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });

  // Wait until the Execute Graph button is on screen.
  const executeBtn = page.getByRole('button', { name: /execute graph/i });
  await executeBtn.waitFor({ state: 'visible', timeout: 30_000 });
  console.log(`[${ms()}ms] Execute Graph button visible — ready to click`);

  // Allow WS to fully establish before we click.
  await page.waitForTimeout(500);

  // CLICK Execute Graph — opens the Sequence Pre-flight modal.
  console.log(`[${ms()}ms] click Execute Graph (opens pre-flight modal)`);
  await executeBtn.click();

  // Fill in any required input fields in the modal.
  const topicInput = page.locator('input[placeholder*="data value"], input[placeholder*="Enter"]').first();
  await topicInput.waitFor({ state: 'visible', timeout: 10_000 });
  await topicInput.fill('What is the impact of LLMs on software engineering productivity?');

  // Click LAUNCH RUN — this is what actually fires POST /api/runs.
  const launchBtn = page.getByRole('button', { name: /launch run/i });
  await launchBtn.waitFor({ state: 'visible', timeout: 5_000 });

  // Allow the modal animation/state-update to settle, then mark T_click.
  await page.waitForTimeout(200);
  const tClick = ms();
  console.log(`[${tClick}ms] >>>>> CLICK Launch Run <<<<<`);
  await launchBtn.click();

  // Wait for first WS frame whose type indicates run progress.
  // We poll the in-memory frames buffer.
  const STATUS_TYPES = new Set(['NODE_STATUS', 'node_status', 'WORKFLOW_STATUS', 'workflow_status']);
  const deadline = Date.now() + 180_000; // 3 min ceiling

  let firstStatusFrame: FrameRecord | null = null;
  let firstAnyAfterClick: FrameRecord | null = null;
  while (Date.now() < deadline) {
    for (const f of frames) {
      if (f.t < tClick) continue;
      if (!firstAnyAfterClick) firstAnyAfterClick = f;
      if (f.type && STATUS_TYPES.has(f.type)) {
        firstStatusFrame = f;
        break;
      }
    }
    if (firstStatusFrame) break;
    await page.waitForTimeout(250);
  }

  // ── REPORT ─────────────────────────────────────────────────────────────
  console.log('\n══════════ TIMING REPORT ══════════');
  console.log(`T_click       = ${tClick} ms (Execute Graph click)`);
  console.log(`T_post        = ${tPostReturn ?? 'NEVER'} ms (POST /api/runs returned)`);
  console.log(`T_first_any   = ${firstAnyAfterClick?.t ?? 'NEVER'} ms (first WS frame after click, type=${firstAnyAfterClick?.type})`);
  console.log(`T_first_status= ${firstStatusFrame?.t ?? 'NEVER'} ms (first NODE_STATUS/WORKFLOW_STATUS, type=${firstStatusFrame?.type}, node=${firstStatusFrame?.node_id}, status=${firstStatusFrame?.status})`);
  if (firstStatusFrame && tPostReturn) {
    console.log(`Δ click→status= ${firstStatusFrame.t - tClick} ms`);
    console.log(`Δ post →status= ${firstStatusFrame.t - tPostReturn} ms`);
  }

  console.log('\n──── First 30 frames after click ────');
  let count = 0;
  for (const f of frames) {
    if (f.t < tClick) continue;
    if (count++ >= 30) break;
    console.log(`  [${f.t}ms] ${f.dir} type=${f.type ?? '?'} node=${f.node_id ?? '-'} status=${f.status ?? '-'} raw=${f.raw.slice(0,80)}`);
  }

  // Persist the report so the user can read it without scrolling Playwright stdout.
  const summary = {
    workspace: WORKSPACE_ID,
    T_click_ms: tClick,
    T_post_ms: tPostReturn,
    T_first_any_ms: firstAnyAfterClick?.t ?? null,
    T_first_status_ms: firstStatusFrame?.t ?? null,
    delta_click_to_status_ms: firstStatusFrame ? firstStatusFrame.t - tClick : null,
    first_status_node: firstStatusFrame?.node_id ?? null,
    first_status_type: firstStatusFrame?.type ?? null,
    frames_after_click: frames.filter((f) => f.t >= tClick).slice(0, 50),
  };
  // Write to /tmp so we can read it from the bash side.
  await page.evaluate((data) => {
    console.log('PLAYWRIGHT_SUMMARY=' + JSON.stringify(data));
  }, summary);

  // Soft-assert: a healthy stack should send the first NODE_STATUS within 10s.
  // If this fires, the user's "3-min gap" is reproduced.
  expect(firstStatusFrame, 'No NODE_STATUS frame received within 3 min after click').not.toBeNull();
  if (firstStatusFrame) {
    const delta = firstStatusFrame.t - tClick;
    expect.soft(delta, `first NODE_STATUS arrived ${delta} ms after click — expected < 10000`).toBeLessThan(10_000);
  }
});
