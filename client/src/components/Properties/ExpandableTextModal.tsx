// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Editable modal with large textarea for text fields (Input Value, Prompt Template, Requirements).
 * Save/Cancel and optional Copy.
 */
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Copy, Check, Save } from 'lucide-react';

interface ExpandableTextModalProps {
  open: boolean;
  title: string;
  value: string;
  onSave: (text: string) => void;
  onClose: () => void;
  onCopy?: (text: string) => void;
  copied?: boolean;
  placeholder?: string;
  textClassName?: string;
}

export function ExpandableTextModal({
  open,
  title,
  value,
  onSave,
  onClose,
  onCopy,
  copied = false,
  placeholder,
  textClassName,
}: ExpandableTextModalProps) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);

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

  const handleSave = () => {
    onSave(draft);
    onClose();
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
                onClick={() => onCopy(draft)}
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                title="Copy to clipboard"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            )}
            <button
              type="button"
              onClick={handleSave}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors"
            >
              <Save size={14} /> Save
            </button>
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
        <div className="flex-1 overflow-hidden flex flex-col min-h-0 p-4">
          <textarea
            className={`w-full flex-1 min-h-[300px] bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono focus:border-indigo-500 outline-none resize-none ${textClassName ?? 'text-slate-300'}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            spellCheck={false}
          />
        </div>
      </div>
    </div>,
    document.body
  );
}
