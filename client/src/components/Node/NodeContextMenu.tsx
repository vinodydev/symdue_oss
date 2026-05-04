/**
 * Context menu for node actions - Matching reference design
 */
import React from 'react';
import { Trash2, Copy, TestTube, ExternalLink } from 'lucide-react';

interface NodeContextMenuProps {
  x: number;
  y: number;
  onDelete: () => void;
  onDuplicate: () => void;
  onTest: () => void;
  onOpenWorkflow?: () => void;
  onClose: () => void;
}

export function NodeContextMenu({
  x,
  y,
  onDelete,
  onDuplicate,
  onTest,
  onOpenWorkflow,
  onClose,
}: NodeContextMenuProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(e) => e.preventDefault()}
      />
      
      {/* Menu */}
      <div
        className="fixed z-50 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl py-1 min-w-[160px]"
        style={{ left: x, top: y }}
        onClick={(e) => e.stopPropagation()}
      >
        {onOpenWorkflow && (
          <>
            <button
              onClick={() => {
                onOpenWorkflow();
                onClose();
              }}
              className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition-colors"
            >
              <ExternalLink size={14} />
              Open workflow
            </button>
            <div className="border-t border-slate-800 my-1" />
          </>
        )}
        <button
          onClick={() => {
            onDuplicate();
            onClose();
          }}
          className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition-colors"
        >
          <Copy size={14} />
          Duplicate
        </button>
        <button
          onClick={() => {
            onTest();
            onClose();
          }}
          className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition-colors"
        >
          <TestTube size={14} />
          Test Node
        </button>
        <div className="border-t border-slate-800 my-1" />
        <button
          onClick={() => {
            onDelete();
            onClose();
          }}
          className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-slate-800 flex items-center gap-2 transition-colors"
        >
          <Trash2 size={14} />
          Delete
        </button>
      </div>
    </>
  );
}
