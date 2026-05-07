// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Tests for EventFormPanel component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventFormPanel } from '../EventFormPanel';

// Mock the API client
vi.mock('@/services/api', () => ({
  api: {
    createEvent: vi.fn().mockResolvedValue({
      id: 'evt-1',
      name: 'Test',
      type: 'interval',
      script: '',
      enabled: true,
      created_at: '2026-01-01T00:00:00',
      updated_at: '2026-01-01T00:00:00',
    }),
    updateEvent: vi.fn().mockResolvedValue({
      id: 'evt-1',
      name: 'Updated',
      type: 'interval',
      script: '',
      enabled: true,
      created_at: '2026-01-01T00:00:00',
      updated_at: '2026-01-01T00:00:00',
    }),
  },
}));

describe('EventFormPanel', () => {
  const onClose = vi.fn();
  const onSaved = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders create form with all fields', () => {
    render(<EventFormPanel onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByPlaceholderText(/My Event/i)).toBeInTheDocument();
    expect(screen.getByText(/New Event/i)).toBeInTheDocument();
  });

  it('shows schedule input for interval type', () => {
    render(<EventFormPanel onClose={onClose} onSaved={onSaved} />);
    // interval is default type
    expect(screen.getByPlaceholderText(/5m, 1h/i)).toBeInTheDocument();
  });

  it('shows cron input when cron type is selected', () => {
    render(<EventFormPanel onClose={onClose} onSaved={onSaved} />);
    // Click the cron type button
    const cronButton = screen.getByText('Cron');
    fireEvent.click(cronButton);
    expect(screen.getByPlaceholderText(/0 9 \* \* MON-FRI/i)).toBeInTheDocument();
  });

  it('shows webhook URL placeholder for webhook type', () => {
    render(<EventFormPanel onClose={onClose} onSaved={onSaved} />);
    const webhookButton = screen.getByText('Webhook');
    fireEvent.click(webhookButton);
    expect(screen.getByPlaceholderText(/HMAC secret/i)).toBeInTheDocument();
  });

  it('calls createEvent API on form submit with name', async () => {
    const { api } = await import('@/services/api');
    render(<EventFormPanel onClose={onClose} onSaved={onSaved} />);

    const nameInput = screen.getByPlaceholderText(/My Event/i);
    fireEvent.change(nameInput, { target: { value: 'My New Event' } });

    const saveButton = screen.getByText(/Create Event/i);
    fireEvent.click(saveButton);

    // API should be called (awaited)
    await vi.waitFor(() => {
      expect(api.createEvent).toHaveBeenCalled();
    });
  });
});
