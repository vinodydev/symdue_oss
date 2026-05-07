// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * View-only modal for expanded JSON/output content with Copy in header.
 * Used for Execution Inputs (History) and Execution Outputs (History).
 */
import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Copy, Check } from 'lucide-react';
import { cn } from '@/utils/cn';

interface OutputModalProps {
  open: boolean;
  title: string;
  content: string;
  onClose: () => void;
  onCopy?: () => void;
  copied?: boolean;
  contentClassName?: string;
}

export function OutputModal({
  open,
  title,
  content,
  onClose,
  onCopy,
  copied = false,
  contentClassName,
}: OutputModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [open, onClose]);

  if (!open) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return createPortal(
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-w-4xl w-full max-h-[85vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 p-4 border-b border-slate-800 shrink-0">
          <h3 className="text-sm font-bold text-slate-200 truncate">{title}</h3>
          <div className="flex items-center gap-2">
            {onCopy && (
              <button
                type="button"
                onClick={onCopy}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="Copy to clipboard"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <pre
            className={cn(
              'text-xs font-mono whitespace-pre-wrap break-words',
              contentClassName ?? 'text-slate-300'
            )}
          >
            {content}
          </pre>
        </div>
      </div>
    </div>,
    document.body
  );
}
