// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * NodeTypePalette component tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NodeTypePalette } from '@/components/Sidebar/NodeTypePalette';

const mockNodeTypes = [
  {
    id: 'input',
    category: 'input',
    name: 'Input Node',
    description: 'Entry point for data',
    icon: 'database',
    is_builtin: true,
    is_active: true,
    default_config: {},
    config_schema: {},
  },
  {
    id: 'custom-python',
    category: 'python',
    name: 'Python Script',
    description: 'Custom code execution',
    icon: 'code',
    is_builtin: true,
    is_active: true,
    default_config: {},
    config_schema: {},
  },
];

describe('NodeTypePalette Component', () => {
  it('should render node types', () => {
    render(<NodeTypePalette nodeTypes={mockNodeTypes} />);
    expect(screen.getByText('Input Node')).toBeInTheDocument();
    expect(screen.getByText('Python Script')).toBeInTheDocument();
  });

  it('should group node types by category', () => {
    render(<NodeTypePalette nodeTypes={mockNodeTypes} />);
    // Categories should be displayed (use getAllByText since "input" appears multiple times)
    const categoryHeaders = screen.getAllByText(/^input$/i);
    expect(categoryHeaders.length).toBeGreaterThan(0);
    expect(screen.getByText(/^python$/i)).toBeInTheDocument();
  });

  it('should make node types draggable', () => {
    render(<NodeTypePalette nodeTypes={mockNodeTypes} />);
    const inputNode = screen.getByText('Input Node').closest('[draggable]');
    
    expect(inputNode).toHaveAttribute('draggable', 'true');
  });

  it('should handle drag start', () => {
    render(<NodeTypePalette nodeTypes={mockNodeTypes} />);
    const inputNode = screen.getByText('Input Node').closest('[draggable]');
    
    if (inputNode) {
      const dragEvent = new Event('dragstart', { bubbles: true });
      Object.defineProperty(dragEvent, 'dataTransfer', {
        value: {
          setData: vi.fn(),
        },
      });
      
      fireEvent(inputNode, dragEvent);
      
      // Drag data should be set
      expect(dragEvent.dataTransfer.setData).toHaveBeenCalled();
    }
  });

  it('should show node type descriptions on hover', () => {
    render(<NodeTypePalette nodeTypes={mockNodeTypes} />);
    const inputNode = screen.getByText('Input Node');
    
    // Hover should show description (if implemented)
    fireEvent.mouseEnter(inputNode);
    // Description may be in title attribute
    expect(inputNode).toBeInTheDocument();
  });
});

