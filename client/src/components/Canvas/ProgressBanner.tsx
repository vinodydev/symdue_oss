// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * "No progress detected" banner.
 *
 * When a run is active (isRunning === true) but no WS frame has arrived for a
 * while, show a small advisory near the top of the canvas. Resolves the user
 * confusion of staring at an idle-looking canvas during loop churn or slow
 * LLM/sandbox cold-starts where no node start/end events fire.
 *
 * Visibility threshold: 30 seconds of WS silence.
 * Self-clears as soon as any frame (including a heartbeat) arrives.
 */
import { useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { useAppStore } from '@/stores';

const STALE_AFTER_MS = 30_000;
const POLL_INTERVAL_MS = 5_000;

export function ProgressBanner() {
  const isRunning = useAppStore((s) => s.isRunning);
  const lastActivityAt = useAppStore((s) => s.lastActivityAt);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isRunning]);

  if (!isRunning) return null;
  if (lastActivityAt == null) return null;
  const silentMs = now - lastActivityAt;
  if (silentMs < STALE_AFTER_MS) return null;

  return (
    <div className="absolute top-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 px-4 py-2 rounded-full bg-amber-950/80 border border-amber-700/60 backdrop-blur-md shadow-lg pointer-events-none">
      <AlertCircle size={14} className="text-amber-400 animate-pulse" />
      <span className="text-[11px] font-semibold text-amber-200">
        No node activity for {Math.floor(silentMs / 1000)}s — workflow may be churning inside a loop
      </span>
    </div>
  );
}
