// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Context menu for edge actions - Matching reference design
 */
import React from 'react';
import { Trash2, Edit } from 'lucide-react';

interface EdgeContextMenuProps {
  x: number;
  y: number;
  onDelete: () => void;
  onEditWeight: () => void;
  onClose: () => void;
}

export function EdgeContextMenu({
  x,
  y,
  onDelete,
  onEditWeight,
  onClose,
}: EdgeContextMenuProps) {
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
        <button
          onClick={() => {
            onEditWeight();
            onClose();
          }}
          className="w-full px-4 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 flex items-center gap-2 transition-colors"
        >
          <Edit size={14} />
          Edit Weight
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
