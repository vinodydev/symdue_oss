// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Send Signal panel — shown in RunHistory when a run is in "waiting" status.
 * Allows sending a signal to resume a waiting workflow.
 */
import React, { useState, useEffect } from 'react';
import { Send, ChevronDown, ChevronRight, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '@/services/api';
import type { WaitStateResponse } from '@/types';
import { cn } from '@/utils/cn';

interface Props {
  runId: string;
  workspaceId: string;
}

export function SendSignalPanel({ runId, workspaceId }: Props) {
  const [waits, setWaits] = useState<WaitStateResponse[]>([]);
  const [expanded, setExpanded] = useState(true);
  const [signal, setSignal] = useState('');
  const [dataJson, setDataJson] = useState('{}');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<'success' | 'error' | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    api.getRunWaits(workspaceId, runId).then(setWaits).catch(() => {});
  }, [runId, workspaceId]);

  // Pre-fill signal name from wait data
  useEffect(() => {
    if (waits.length > 0 && !signal) {
      const needed = waits[0].signals_needed;
      if (needed && needed.length > 0) {
        setSignal(needed[0]);
      }
    }
  }, [waits, signal]);

  const handleSend = async () => {
    setSending(true);
    setResult(null);
    setErrorMsg('');
    try {
      const data = JSON.parse(dataJson);
      await api.sendSignalToRun(runId, workspaceId, signal || 'signal', data);
      setResult('success');
      setTimeout(() => setResult(null), 3000);
    } catch (err: any) {
      setResult('error');
      setErrorMsg(err?.message || 'Failed to send signal');
    } finally {
      setSending(false);
    }
  };

  if (!waits.length) return null;

  const activeWait = waits.find((w) => !w.satisfied) || waits[0];

  return (
    <div className="mx-2 mb-2 border border-amber-500/30 rounded-lg overflow-hidden bg-amber-500/5">
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-amber-400 hover:bg-amber-500/10 transition-colors"
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Send size={12} />
        Send Signal
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {/* Wait info */}
          <div className="text-[10px] text-slate-400 space-y-0.5">
            <div>Channel: <span className="text-amber-300 font-mono">{activeWait.channel}</span></div>
            <div>Mode: <span className="text-slate-300">{activeWait.mode}</span></div>
            {activeWait.signals_needed && activeWait.signals_needed.length > 0 && (
              <div>Needs: <span className="text-slate-300">{activeWait.signals_needed.join(', ')}</span></div>
            )}
            {activeWait.timeout_at && (
              <div>Timeout: <span className="text-slate-300">{new Date(activeWait.timeout_at).toLocaleString()}</span></div>
            )}
          </div>

          {/* Signal name input */}
          <input
            type="text"
            value={signal}
            onChange={(e) => setSignal(e.target.value)}
            placeholder="Signal name"
            className="w-full px-2 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
          />

          {/* Data JSON input */}
          <textarea
            value={dataJson}
            onChange={(e) => setDataJson(e.target.value)}
            placeholder='{"key": "value"}'
            rows={2}
            className="w-full px-2 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 font-mono resize-none"
          />

          {/* Send button + status */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || !signal.trim()}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors',
                'bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {sending ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Send size={12} />
              )}
              Send
            </button>

            {result === 'success' && (
              <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                <CheckCircle2 size={10} />
                Signal sent. Workflow resuming.
              </span>
            )}
            {result === 'error' && (
              <span className="flex items-center gap-1 text-[10px] text-red-400">
                <AlertCircle size={10} />
                {errorMsg}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
