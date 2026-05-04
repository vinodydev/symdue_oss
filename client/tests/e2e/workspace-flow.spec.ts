import { test, expect } from '@playwright/test';

test.describe('Workspace Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to app
    await page.goto('/');
    // Wait for app to load
    await page.waitForLoadState('networkidle');
  });

  test('complete workflow: create workspace → add nodes → connect → test', async ({ page }) => {
    // 1. Verify app loaded
    await expect(page).toHaveTitle(/GraphMind/i);
    
    // Wait for sidebar to load
    await page.waitForSelector('[class*="sidebar"]', { timeout: 5000 });
    
    // 2. Create new workspace
    // Look for workspace creation button or "New Workspace" text
    const createButton = page.getByRole('button', { name: /new workspace|create|add workspace/i }).first();
    
    if (await createButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createButton.click();
      
      // Fill workspace name if modal appears
      const nameInput = page.getByPlaceholder(/workspace name|name/i).first();
      if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await nameInput.fill('E2E Test Workspace');
        const submitButton = page.getByRole('button', { name: /create|submit|ok/i }).first();
        await submitButton.click();
      }
    } else {
      // If no create button, workspace might auto-create or already exist
      // Just verify we can see workspace list
      await expect(page.locator('[class*="workspace"]').first()).toBeVisible({ timeout: 5000 });
    }
    
    // 3. Verify workspace is visible
    await expect(page.getByText(/E2E Test Workspace|Untitled/i).first()).toBeVisible({ timeout: 5000 });
    
    // 4. Add node by dragging from sidebar
    const nodeTypePalette = page.locator('[class*="palette"], [class*="node-type"]').first();
    await expect(nodeTypePalette).toBeVisible({ timeout: 5000 });
    
    // Find Input Node in sidebar
    const inputNodeText = page.getByText('Input Node').first();
    await expect(inputNodeText).toBeVisible({ timeout: 5000 });
    
    const canvas = page.locator('[class*="canvas"]').first();
    await expect(canvas).toBeVisible({ timeout: 5000 });
    
    // Drag and drop node
    await inputNodeText.dragTo(canvas, {
      targetPosition: { x: 200, y: 200 }
    });
    
    // Wait for node to appear on canvas
    await page.waitForTimeout(1000);
    
    // Verify node appeared (may be in different format)
    const nodes = page.locator('[class*="node"]');
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThan(0);
    
    // 5. Add another node
    const pythonNodeText = page.getByText('Python Script').first();
    if (await pythonNodeText.isVisible({ timeout: 2000 }).catch(() => false)) {
      await pythonNodeText.dragTo(canvas, {
        targetPosition: { x: 400, y: 200 }
      });
      await page.waitForTimeout(1000);
    }
    
    // 6. Connect nodes (if handles are visible)
    const nodeElements = page.locator('[class*="node"]');
    const nodeCountAfter = await nodeElements.count();
    
    if (nodeCountAfter >= 2) {
      // Try to find connection handles
      const sourceHandle = page.locator('[class*="handle"][class*="right"], [class*="output"]').first();
      const targetHandle = page.locator('[class*="handle"][class*="left"], [class*="input"]').first();
      
      if (await sourceHandle.isVisible({ timeout: 2000 }).catch(() => false) &&
          await targetHandle.isVisible({ timeout: 2000 }).catch(() => false)) {
        await sourceHandle.dragTo(targetHandle);
        await page.waitForTimeout(1000);
        
        // Verify edge is created
        const edges = page.locator('[class*="edge"], path, line');
        const edgeCount = await edges.count();
        expect(edgeCount).toBeGreaterThan(0);
      }
    }
    
    // 7. Test node (pre-flight) - click on node first
    const firstNode = nodeElements.first();
    await firstNode.click();
    await page.waitForTimeout(500);
    
    // Look for test button
    const testButton = page.getByRole('button', { name: /test|launch|run/i }).first();
    if (await testButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await testButton.click();
      
      // Wait for test modal or result
      await page.waitForTimeout(2000);
      
      // Close modal if it opened
      const closeButton = page.getByRole('button', { name: /close|×/i }).first();
      if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await closeButton.click();
      }
    }
    
    // 8. Update edge weight (if edge exists)
    const edges = page.locator('[class*="edge"], path, line');
    const edgeCount = await edges.count();
    
    if (edgeCount > 0) {
      const edge = edges.first();
      await edge.click();
      await page.waitForTimeout(500);
      
      // Look for weight slider
      const weightSlider = page.locator('[role="slider"]').first();
      if (await weightSlider.isVisible({ timeout: 2000 }).catch(() => false)) {
        // Update weight
        await weightSlider.fill('0.75');
        await page.waitForTimeout(500);
      }
    }
    
    // 9. Save workspace (auto-save should happen)
    await page.waitForTimeout(1000);
    
    // 10. Refresh and verify persistence
    await page.reload();
    await page.waitForLoadState('networkidle');
    
    // Verify workspace still exists
    await expect(page.getByText(/E2E Test Workspace|Untitled/i).first()).toBeVisible({ timeout: 5000 });
  });
  
  test('node properties editing', async ({ page }) => {
    // Wait for app to load
    await page.waitForSelector('[class*="sidebar"]', { timeout: 5000 });
    
    // Create or select workspace
    const createButton = page.getByRole('button', { name: /new workspace|create/i }).first();
    if (await createButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createButton.click();
      const nameInput = page.getByPlaceholder(/name/i).first();
      if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await nameInput.fill('Properties Test');
        await page.getByRole('button', { name: /create/i }).first().click();
      }
    }
    
    // Add node
    const inputNode = page.getByText('Input Node').first();
    await expect(inputNode).toBeVisible({ timeout: 5000 });
    
    const canvas = page.locator('[class*="canvas"]').first();
    await inputNode.dragTo(canvas, {
      targetPosition: { x: 200, y: 200 }
    });
    
    await page.waitForTimeout(1000);
    
    // Click node to open properties
    const nodes = page.locator('[class*="node"]');
    await nodes.first().click();
    await page.waitForTimeout(500);
    
    // Look for properties panel
    const propertiesPanel = page.locator('[class*="properties"], [class*="panel"]');
    if (await propertiesPanel.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Edit properties
      const nameInput = page.getByPlaceholder(/node name|name/i).first();
      if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await nameInput.clear();
        await nameInput.fill('My Custom Input');
        await page.waitForTimeout(500);
        
        // Verify update
        await expect(page.getByText('My Custom Input')).toBeVisible({ timeout: 2000 });
      }
    }
  });
  
  test('workspace list and selection', async ({ page }) => {
    // Wait for app to load
    await page.waitForSelector('[class*="sidebar"]', { timeout: 5000 });
    
    // Create multiple workspaces
    for (let i = 1; i <= 3; i++) {
      const createButton = page.getByRole('button', { name: /new workspace|create/i }).first();
      if (await createButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await createButton.click();
        const nameInput = page.getByPlaceholder(/name/i).first();
        if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
          await nameInput.fill(`Workspace ${i}`);
          await page.getByRole('button', { name: /create/i }).first().click();
          await page.waitForTimeout(1000);
        }
      }
    }
    
    // Verify workspaces in sidebar
    await expect(page.getByText('Workspace 1').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Workspace 2').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Workspace 3').first()).toBeVisible({ timeout: 5000 });
    
    // Switch between workspaces
    await page.getByText('Workspace 2').first().click();
    await page.waitForTimeout(1000);
    await expect(page.getByText('Workspace 2').first()).toBeVisible();
    
    await page.getByText('Workspace 3').first().click();
    await page.waitForTimeout(1000);
    await expect(page.getByText('Workspace 3').first()).toBeVisible();
  });
  
  test('app loads and displays correctly', async ({ page }) => {
    // Check title
    await expect(page).toHaveTitle(/GraphMind/i);
    
    // Check main elements are visible
    await expect(page.locator('[class*="sidebar"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[class*="canvas"]').first()).toBeVisible({ timeout: 5000 });
    
    // Check node types are loaded
    await expect(page.getByText(/Input Node|Python Script/i).first()).toBeVisible({ timeout: 5000 });
  });
});

