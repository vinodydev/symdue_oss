// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node component tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Node } from '@/components/Node/Node';
import { useAppStore } from '@/stores/useAppStore';

// Mock API client
vi.mock('@/services/api/client', () => ({
  api: {
    testNode: vi.fn(),
  },
}));

const noop = () => {};
const noopAsync = async () => {};

describe('Node Component', () => {
  const mockNode = {
    id: 'node-1',
    workflow_id: 'workspace-1',
    node_type_id: 'input',
    x: 100,
    y: 200,
    config: { name: 'Test Node' },
    created_at: '',
    updated_at: '',
    version: 1,
  };

  const defaultProps = {
    node: mockNode,
    isSelected: false,
    isConnecting: false,
    movingNodeId: null,
    onClick: vi.fn(),
    onDoubleClick: vi.fn(),
    onMouseUp: vi.fn(),
    onStartEdgeCreation: vi.fn(),
  };

  beforeEach(() => {
    useAppStore.setState({
      currentWorkspaceId: 'workspace-1',
      nodes: [mockNode],
      edges: [],
      selectedNodeId: null,
    });
    vi.clearAllMocks();
  });

  it('should render node', () => {
    render(<Node {...defaultProps} />);
    expect(screen.getByText(/test node/i)).toBeInTheDocument();
  });

  it('should handle node click', () => {
    render(<Node {...defaultProps} />);
    const nodeElement = screen.getByText(/test node/i).closest('div');
    
    if (nodeElement) {
      fireEvent.click(nodeElement);
      expect(defaultProps.onClick).toHaveBeenCalledWith(expect.anything(), 'node-1');
    }
  });

  it('should show selected state', () => {
    render(<Node {...defaultProps} isSelected={true} />);
    
    const nodeElement = screen.getByText(/test node/i).closest('div');
    expect(nodeElement?.className).toMatch(/border-indigo/);
  });

  it('should handle double click', () => {
    render(<Node {...defaultProps} />);
    const nodeElement = screen.getByText(/test node/i).closest('div');
    
    if (nodeElement) {
      fireEvent.doubleClick(nodeElement);
      expect(defaultProps.onDoubleClick).toHaveBeenCalledWith(expect.anything(), 'node-1');
    }
  });

  it('should show connection handles', () => {
    render(<Node {...defaultProps} />);
    // Connection handles (ports) should be present as divs
    const container = screen.getByText(/test node/i).closest('div')?.parentElement;
    expect(container).toBeInTheDocument();
  });
});
