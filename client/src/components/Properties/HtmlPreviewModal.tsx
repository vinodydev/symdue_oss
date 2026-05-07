// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Fullscreen modal for rendering HTML inside a sandboxed iframe.
 * Used by html-viewer nodes (issue17) for an expanded preview.
 */
import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Copy, Check } from 'lucide-react';

interface HtmlPreviewModalProps {
  open: boolean;
  title: string;
  html: string;
  onClose: () => void;
  onCopy?: () => void;
  copied?: boolean;
}

export function HtmlPreviewModal({
  open,
  title,
  html,
  onClose,
  onCopy,
  copied = false,
}: HtmlPreviewModalProps) {
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
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col w-[95vw] h-[92vh] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
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
                title="Copy HTML source"
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
        <div className="flex-1 overflow-hidden bg-white">
          <iframe
            sandbox=""
            srcDoc={html}
            className="w-full h-full border-0"
            title="HTML preview (expanded)"
          />
        </div>
      </div>
    </div>,
    document.body
  );
}
