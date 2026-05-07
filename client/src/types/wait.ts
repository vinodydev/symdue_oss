// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Wait node types
 */

export type WaitMode = 'signal' | 'any' | 'all' | 'time' | 'until';

export interface WaitNodeConfig {
  channel: string;
  mode: WaitMode;
  signals?: string[];
  timeout?: string;
  duration?: string;
  until?: string;
}

export interface WaitStateResponse {
  id: string;
  run_id: string;
  node_id: string;
  channel: string;
  mode: string;
  signals_needed?: string[];
  signals_received?: string[];
  timeout_at?: string;
  satisfied: boolean;
  created_at: string;
}
