// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
//
// Diagnostic: after a run is in progress, does reloading the page restore
// node statuses on the canvas? User-reported symptom: "ui is not loading
// last state" after docker down/up.
//
// Test plan:
//   1. Open canvas, kick off a run, wait for ≥3 nodes to complete.
//   2. Capture the canvas DOM state (which nodes are 'success').
//   3. Hard-reload the page.
//   4. Wait for the canvas to mount + the first runs/runId fetch to finish.
//   5. Re-check the DOM. Expect the previously-completed nodes to still be 'success'.
//
import { expect, test } from '@playwright/test';

const WORKSPACE_ID = '1a9aac5b-db69-42cc-9023-c8569ae75417';
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:3000';

test.use({ viewport: { width: 1400, height: 900 } });

// Read the React Flow node DOM and pull each node's id + the css classes that
// indicate status. The Canvas component sets classes like
// `node-status-success`, `node-status-running`, `node-status-error`, etc.
async function readCanvasNodeStatuses(page: any): Promise<Record<string, string[]>> {
  return page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('[data-id]')) as HTMLElement[];
    const out: Record<string, string[]> = {};
    for (const el of nodes) {
      const id = el.getAttribute('data-id') || '';
      if (!id || id.startsWith('reactflow__')) continue;
      // Pull anything class-name-y under the node.
      const classes = Array.from(el.classList);
      const inner = el.querySelector('[class*="status"]');
      if (inner) classes.push(...Array.from(inner.classList));
      out[id] = classes.filter((c) => /(status|success|running|error|waiting|blocked|completed)/i.test(c));
    }
    return out;
  });
}

test('canvas restores node statuses after page reload during active run', async ({ page, context }) => {
  test.setTimeout(180_000);

  await context.addInitScript((wsId) => {
    try { window.localStorage.setItem('graphmind_current_workspace_id', wsId); } catch (_) {}
  }, WORKSPACE_ID);

  console.log('[STEP 1] Open canvas + start a run');
  await page.goto(FRONTEND, { waitUntil: 'domcontentloaded' });

  const executeBtn = page.getByRole('button', { name: /execute graph/i });
  await executeBtn.waitFor({ state: 'visible', timeout: 30_000 });
  await executeBtn.click();

  const topicInput = page.locator('input[placeholder*="data value"], input[placeholder*="Enter"]').first();
  await topicInput.waitFor({ state: 'visible', timeout: 10_000 });
  await topicInput.fill('reload-preservation E2E test topic');

  const launchBtn = page.getByRole('button', { name: /launch run/i });
  await launchBtn.click();

  console.log('[STEP 2] Wait 18s for nodes to start completing');
  await page.waitForTimeout(18_000);

  // Pull the run's snapshot from the API directly; that's the source of truth
  // for what the canvas SHOULD be showing.
  const beforeSnapshot = await page.evaluate(async (wsId) => {
    const r = await fetch(`/api/runs/${wsId}?summary=true`).then(x => x.json());
    if (!r.length) return { runs: 0, completed: 0, runId: null };
    const active = r.find((x: any) => x.status === 'running' || x.status === 'completed' || x.status === 'success');
    if (!active) return { runs: r.length, completed: 0, runId: null };
    const full = await fetch(`/api/runs/${wsId}/${active.run_id}`).then(x => x.json());
    const nodeOutputs = full.snapshot?.node_outputs || {};
    return { runs: r.length, completed: Object.keys(nodeOutputs).length, runId: active.run_id, status: active.status };
  }, WORKSPACE_ID);
  console.log(`[STEP 2] Backend snapshot: run=${beforeSnapshot.runId?.slice(0,8)} status=${beforeSnapshot.status} nodes_completed=${beforeSnapshot.completed}`);

  // Screenshot before reload.
  await page.screenshot({ path: 'test-results/pre-reload-canvas.png' });
  console.log('[STEP 2] saved test-results/pre-reload-canvas.png');

  console.log('[STEP 3] Reload page (simulates user F5)');
  await page.reload({ waitUntil: 'domcontentloaded' });

  // Wait for canvas to remount, runs/snapshot fetch to land, seeding to apply.
  await page.waitForTimeout(5_000);

  await page.screenshot({ path: 'test-results/post-reload-canvas.png' });
  console.log('[STEP 4] saved test-results/post-reload-canvas.png');

  // Pull snapshot again post-reload. If the run is still alive on the backend,
  // the snapshot stays in DB regardless of frontend. The question is whether
  // the FRONTEND CANVAS reflects it. Inspect the React state via window.
  const afterFrontendState = await page.evaluate(() => {
    // Try to read from the Zustand store if it's exposed on window.
    const store = (window as any).__APP_STORE__;
    if (store && store.getState) {
      const s = store.getState();
      return {
        runs: (s.runs || []).length,
        currentRunId: s.currentRunId,
        nodeStatuses: s.nodeStatuses,
        nodes_with_status: Object.keys(s.nodeStatuses || {}).length,
      };
    }
    return { error: 'store not exposed on window' };
  });
  console.log(`[STEP 4] Frontend after reload: ${JSON.stringify(afterFrontendState)}`);

  console.log('\n══════════ RELOAD STATE REPORT ══════════');
  console.log(`Backend snapshot at reload time: ${beforeSnapshot.completed} nodes completed (run ${beforeSnapshot.runId?.slice(0,8)})`);
  console.log(`Frontend after reload + 5s wait: ${JSON.stringify(afterFrontendState)}`);
  console.log(`Compare pre-reload-canvas.png vs post-reload-canvas.png in test-results/`);

  // The behavioral test: if backend has > 0 nodes done, frontend should
  // re-seed the canvas with those statuses after reload.
  if (beforeSnapshot.completed > 0) {
    expect.soft(
      (afterFrontendState as any).nodes_with_status ?? -1,
      `Backend has ${beforeSnapshot.completed} completed nodes but frontend nodeStatuses is ${(afterFrontendState as any).nodes_with_status}`,
    ).toBeGreaterThan(0);
  }
});
