// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Canvas component tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Canvas } from '@/components/Canvas/Canvas';
import { useAppStore } from '@/stores/useAppStore';

// Mock the API client
vi.mock('@/services/api/client', () => ({
  api: {
    createNode: vi.fn(),
    createEdge: vi.fn(),
  },
}));

// Mock WebSocket
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    connected: false,
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  }),
}));

describe('Canvas Component', () => {
  beforeEach(() => {
    // Reset store
    useAppStore.setState({
      workspaces: [],
      currentWorkspaceId: null,
      nodes: [],
      edges: [],
      transform: { x: 0, y: 0, k: 1 },
    });
  });

  it('should render canvas without workspace', () => {
    render(<Canvas />);
    expect(screen.getByText(/no workspace selected/i)).toBeInTheDocument();
  });

  it('should render canvas with workspace', () => {
    useAppStore.setState({
      currentWorkspaceId: 'workspace-1',
      nodes: [],
      edges: [],
    });

    render(<Canvas />);
    // Canvas should render (no error message)
    expect(screen.queryByText(/no workspace selected/i)).not.toBeInTheDocument();
  });

  it('should handle drag and drop node creation', async () => {
    const { api } = await import('@/services/api/client');
    const mockCreateNode = vi.fn().mockResolvedValue({
      id: 'node-1',
      workflow_id: 'workspace-1',
      node_type_id: 'input',
      x: 100,
      y: 200,
      config: {},
      created_at: '',
      updated_at: '',
      version: 1,
    });
    (api.createNode as any) = mockCreateNode;

    useAppStore.setState({
      currentWorkspaceId: 'workspace-1',
      nodes: [],
      edges: [],
    });

    const { container } = render(<Canvas />);
    const canvas = container.querySelector('[class*="canvas"]') || container;

    // Simulate drag and drop
    const nodeTypeData = JSON.stringify({
      id: 'input',
      name: 'Input Node',
      category: 'input',
    });

    fireEvent.drop(canvas, {
      dataTransfer: {
        getData: () => nodeTypeData,
      },
      clientX: 100,
      clientY: 200,
    });

    await waitFor(() => {
      expect(mockCreateNode).toHaveBeenCalled();
    });
  });

  it('should handle panning', () => {
    useAppStore.setState({
      currentWorkspaceId: 'workspace-1',
      nodes: [],
      edges: [],
    });

    const { container } = render(<Canvas />);
    const canvas = container.querySelector('[class*="canvas"]') || container;

    // Simulate mouse down and move for panning
    fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 });
    fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200 });
    fireEvent.mouseUp(canvas);

    // Transform should be updated
    const transform = useAppStore.getState().transform;
    expect(transform.x).not.toBe(0);
    expect(transform.y).not.toBe(0);
  });

  it('should handle zoom', () => {
    useAppStore.setState({
      currentWorkspaceId: 'workspace-1',
      nodes: [],
      edges: [],
    });

    const { container } = render(<Canvas />);
    const canvas = container.querySelector('[class*="canvas"]') || container;

    // Simulate wheel event for zoom
    fireEvent.wheel(canvas, {
      deltaY: -100,
      clientX: 100,
      clientY: 100,
    });

    // Transform scale should be updated
    const transform = useAppStore.getState().transform;
    expect(transform.k).not.toBe(1);
  });
});

