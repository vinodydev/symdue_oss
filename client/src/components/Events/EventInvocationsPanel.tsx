/**
 * Panel showing invocation history for an event.
 */
import React, { useState, useEffect } from 'react';
import { X, CheckCircle2, XCircle, Loader2, Clock } from 'lucide-react';
import { api } from '@/services/api';
import type { FlowEvent, EventInvocation, EventInvocationDetail } from '@/types';
import { cn } from '@/utils/cn';

interface EventInvocationsPanelProps {
  event: FlowEvent;
  onClose: () => void;
}

export function EventInvocationsPanel({ event, onClose }: EventInvocationsPanelProps) {
  const [invocations, setInvocations] = useState<EventInvocation[]>([]);
  const [selectedInv, setSelectedInv] = useState<EventInvocationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    loadInvocations();
  }, [event.id]);

  const loadInvocations = async () => {
    setLoading(true);
    try {
      const data = await api.getEventInvocations(event.id);
      setInvocations(data);
    } catch (err) {
      console.error('Failed to load invocations:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectInv = async (inv: EventInvocation) => {
    setLoadingDetail(true);
    try {
      const detail = await api.getEventInvocation(event.id, inv.id);
      setSelectedInv(detail);
    } catch (err) {
      console.error('Failed to load invocation detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDuration = (ms?: number | null) => {
    if (ms == null) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatDate = (s?: string | null) => {
    if (!s) return '—';
    return new Date(s).toLocaleString();
  };

  return (
    <div className="fixed inset-y-0 right-0 w-[700px] bg-slate-900 border-l border-slate-800 flex flex-col z-50 shadow-2xl animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div>
          <h2 className="text-sm font-bold text-slate-200">Invocations</h2>
          <p className="text-[10px] text-slate-500">{event.name}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-slate-500 hover:text-slate-300 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Invocation list */}
        <div className="w-64 border-r border-slate-800 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">History</span>
            <button
              type="button"
              onClick={loadInvocations}
              className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
            >
              Refresh
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={18} className="text-slate-500 animate-spin" />
              </div>
            ) : invocations.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500">No invocations yet</div>
            ) : (
              invocations.map((inv) => (
                <button
                  key={inv.id}
                  type="button"
                  onClick={() => handleSelectInv(inv)}
                  className={cn(
                    'w-full text-left px-3 py-2.5 border-b border-slate-800/50 hover:bg-slate-800/40 transition-colors',
                    selectedInv?.id === inv.id ? 'bg-slate-800/60' : ''
                  )}
                >
                  <div className="flex items-center gap-2">
                    {inv.error ? (
                      <XCircle size={12} className="text-red-400 shrink-0" />
                    ) : (
                      <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
                    )}
                    <span className="text-[10px] text-slate-400 truncate flex-1">
                      {formatDate(inv.started_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 pl-4">
                    <span className="text-[10px] text-slate-500 capitalize">{inv.triggered_by || '—'}</span>
                    <span className="text-[10px] text-slate-600">{formatDuration(inv.duration_ms)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Detail view */}
        <div className="flex-1 overflow-y-auto p-4">
          {loadingDetail ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={18} className="text-slate-500 animate-spin" />
            </div>
          ) : !selectedInv ? (
            <div className="py-8 text-center text-xs text-slate-500">
              Select an invocation to view details
            </div>
          ) : (
            <div className="space-y-4">
              {/* Meta */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-800/40 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Triggered By</div>
                  <div className="text-xs text-slate-300 capitalize">{selectedInv.triggered_by || '—'}</div>
                </div>
                <div className="p-3 bg-slate-800/40 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Duration</div>
                  <div className="text-xs text-slate-300">{formatDuration(selectedInv.duration_ms)}</div>
                </div>
              </div>

              {/* Error */}
              {selectedInv.error && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <div className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-1">Error</div>
                  <pre className="text-xs text-red-300 font-mono whitespace-pre-wrap break-words">{selectedInv.error}</pre>
                  {selectedInv.traceback && (
                    <pre className="mt-2 text-[10px] text-red-300/60 font-mono whitespace-pre-wrap break-words">{selectedInv.traceback}</pre>
                  )}
                </div>
              )}

              {/* State before/after */}
              {(selectedInv.state_before || selectedInv.state_after) && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">State Before</div>
                    <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-[10px] text-slate-400 font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                      {JSON.stringify(selectedInv.state_before, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">State After</div>
                    <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-[10px] text-emerald-400/70 font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                      {JSON.stringify(selectedInv.state_after, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Log output */}
              {selectedInv.log_output && (
                <div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Log Output</div>
                  <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-[10px] text-slate-300 font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                    {selectedInv.log_output}
                  </pre>
                </div>
              )}

              {/* Runtime calls */}
              {selectedInv.runtime_calls && selectedInv.runtime_calls.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                    Runtime Calls ({selectedInv.runtime_calls.length})
                  </div>
                  <div className="space-y-1">
                    {selectedInv.runtime_calls.map((call, idx) => (
                      <div key={idx} className="p-2 bg-slate-950 border border-slate-800 rounded-lg">
                        <code className="text-[10px] text-purple-300">{call.method}</code>
                        {call.result != null && (
                          <span className="text-[10px] text-slate-500 ml-2">→ {JSON.stringify(call.result)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
