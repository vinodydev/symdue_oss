// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Modal to view a run's node outputs (from snapshot). Copy per node.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Copy, Check } from 'lucide-react';
import type { Run, Node } from '@/types';

interface RunOutputsModalProps {
  open: boolean;
  run: Run | null;
  nodes: Node[];
  onClose: () => void;
}

export function RunOutputsModal({ open, run, nodes, onClose }: RunOutputsModalProps) {
  const [copiedNodeId, setCopiedNodeId] = useState<string | null>(null);

  const copyOutput = useCallback((nodeId: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedNodeId(nodeId);
      setTimeout(() => setCopiedNodeId(null), 2000);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [open, onClose]);

  if (!open || !run) return null;

  const nodeOutputs = run.snapshot?.node_outputs ?? {};
  const snapshotNodes = run.snapshot?.nodes as Array<{ id: string; name?: string }> | undefined;
  const getNodeName = (nodeId: string) => {
    const n = nodes.find((x) => x.id === nodeId);
    if (n) return n.name || n.id;
    const sn = snapshotNodes?.find((x) => x.id === nodeId);
    return sn?.name ?? nodeId;
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const entries = Object.entries(nodeOutputs);

  return createPortal(
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-w-2xl w-full max-h-[85vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 p-4 border-b border-slate-800 shrink-0">
          <h3 className="text-sm font-bold text-slate-200 truncate">
            Outputs: {run.label || 'Run'} {run.started_at && `(${new Date(run.started_at).toLocaleString()})`}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
          {entries.length === 0 ? (
            <p className="text-xs text-slate-500 italic">No node outputs in this run.</p>
          ) : (
            entries.map(([nodeId, output]) => {
              const text = typeof output === 'string' ? output : JSON.stringify(output, null, 2);
              const name = getNodeName(nodeId);
              return (
                <div key={nodeId} className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950">
                  <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900/50">
                    <span className="text-xs font-bold text-slate-300 truncate">{name}</span>
                    <button
                      type="button"
                      onClick={() => copyOutput(nodeId, text)}
                      className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white shrink-0"
                      title="Copy output"
                    >
                      {copiedNodeId === nodeId ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                  <pre className="p-3 text-xs text-emerald-300 font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                    {text}
                  </pre>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
