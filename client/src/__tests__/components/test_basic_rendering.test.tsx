// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Basic component rendering tests
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AppLayout } from '@/components/AppLayout';
import { Sidebar } from '@/components/Sidebar/Sidebar';
import { PropertiesPanel } from '@/components/Properties/PropertiesPanel';

describe('Component Rendering', () => {
  describe('AppLayout', () => {
    it('should render without crashing', () => {
      render(
        <AppLayout>
          <div>Test Content</div>
        </AppLayout>
      );
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('should render header', () => {
      render(
        <AppLayout>
          <div>Content</div>
        </AppLayout>
      );
      expect(screen.getByText('GraphMind Orchestrator')).toBeInTheDocument();
    });
  });

  describe('Sidebar', () => {
    it('should render without crashing', () => {
      render(<Sidebar />);
      // Sidebar should render (may show loading state)
    });
  });

  describe('PropertiesPanel', () => {
    it('should render without crashing', () => {
      render(<PropertiesPanel />);
      expect(screen.getByText('Properties')).toBeInTheDocument();
    });

    it('should show message when nothing selected', () => {
      render(<PropertiesPanel />);
      expect(screen.getByText(/Select a node or edge to edit properties/i)).toBeInTheDocument();
    });
  });
});

