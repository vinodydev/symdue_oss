// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Tests for WaitNodeProperties component
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WaitNodeProperties } from '../WaitNodeProperties';

describe('WaitNodeProperties', () => {
  const defaultConfig = {
    channel: '',
    mode: 'signal',
    signals: [],
    timeout: '',
  };

  it('renders channel input and mode dropdown', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={defaultConfig} onConfigChange={onConfigChange} />);
    expect(screen.getByPlaceholderText(/e\.g\. order_approval/i)).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows signals list for signal mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'signal' }} onConfigChange={onConfigChange} />);
    expect(screen.getByText(/Signal Name/i)).toBeInTheDocument();
    expect(screen.getByText(/Add/i)).toBeInTheDocument();
  });

  it('shows signals list for any mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'any' }} onConfigChange={onConfigChange} />);
    expect(screen.getByText(/Signal Names/i)).toBeInTheDocument();
  });

  it('shows signals list for all mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'all' }} onConfigChange={onConfigChange} />);
    expect(screen.getByText(/Signal Names/i)).toBeInTheDocument();
  });

  it('hides signals list for time mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'time' }} onConfigChange={onConfigChange} />);
    expect(screen.queryByText(/Signal Name/i)).not.toBeInTheDocument();
  });

  it('hides signals list for until mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'until' }} onConfigChange={onConfigChange} />);
    expect(screen.queryByText(/Signal Name/i)).not.toBeInTheDocument();
  });

  it('shows duration input for time mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'time' }} onConfigChange={onConfigChange} />);
    expect(screen.getByText(/Duration/i)).toBeInTheDocument();
  });

  it('shows until datetime input for until mode', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={{ ...defaultConfig, mode: 'until' }} onConfigChange={onConfigChange} />);
    expect(screen.getByText(/Resume At/i)).toBeInTheDocument();
  });

  it('calls onConfigChange when channel is updated', () => {
    const onConfigChange = vi.fn();
    render(<WaitNodeProperties config={defaultConfig} onConfigChange={onConfigChange} />);

    const channelInput = screen.getByPlaceholderText(/e\.g\. order_approval/i);
    fireEvent.change(channelInput, { target: { value: 'my_channel' } });

    expect(onConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ channel: 'my_channel' })
    );
  });
});
