// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Form for node type metadata (name, description, icon, category, supports iterator).
 * Used in NodeTypeDetailCode (right panel) and NodeTypeDetailPropertiesOnly.
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { NodeType, NodeTypeUpdate } from '@/types';
import { supportsIterator } from '@/utils/nodeUtils';
import { cn } from '@/utils/cn';

interface NodeTypePropertiesFormProps {
  nodeType: NodeType;
  onSaved: () => void;
  /** When true, form is in a side panel (e.g. next to code editor); when false, full-width. */
  compact?: boolean;
}

export function NodeTypePropertiesForm({
  nodeType,
  onSaved,
  compact = false,
}: NodeTypePropertiesFormProps) {
  const [name, setName] = useState(nodeType.name || '');
  const [description, setDescription] = useState(nodeType.description || '');
  const [icon, setIcon] = useState(nodeType.icon || '');
  const [category, setCategory] = useState(nodeType.category || '');
  const [savesIterator, setSavesIterator] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(nodeType.name || '');
    setDescription(nodeType.description || '');
    setIcon(nodeType.icon || '');
    setCategory(nodeType.category || '');
    setSavesIterator(!!(nodeType.config_schema as any)?.supports_iterator);
  }, [nodeType.id, nodeType.name, nodeType.description, nodeType.icon, nodeType.category, nodeType.config_schema]);

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    const payload: NodeTypeUpdate = {
      name: name || undefined,
      description: description || undefined,
      icon: icon || undefined,
      category: category || undefined,
    };
    if (!nodeType.is_builtin) {
      payload.config_schema = {
        ...(nodeType.config_schema || {}),
        supports_iterator: savesIterator,
      };
    }
    try {
      await api.updateNodeType(nodeType.id, payload);
      onSaved();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const canEdit = !nodeType.is_builtin;

  return (
    <div className={cn('space-y-6', compact && 'min-w-0')}>
      <div className="space-y-4">
        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">ID</label>
          <p className="text-sm text-slate-400 font-mono">{nodeType.id}</p>
        </div>

        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={nodeType.is_builtin}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed"
          />
        </div>

        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          />
        </div>

        <div>
          <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Icon</label>
          <input
            type="text"
            value={icon}
            onChange={(e) => setIcon(e.target.value)}
            placeholder="e.g. code, database"
            className="w-full px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        {canEdit && (
          <div>
            <label className="text-[10px] font-bold text-slate-500 uppercase block mb-1 tracking-widest">Category</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        )}

        {!nodeType.is_builtin && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="supports_iterator"
              checked={savesIterator}
              onChange={(e) => setSavesIterator(e.target.checked)}
              className="rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-500"
            />
            <label htmlFor="supports_iterator" className="text-sm text-slate-300">Supports iterator</label>
          </div>
        )}

        {nodeType.is_builtin && (
          <p className="text-xs text-slate-500">Built-in type: only name, description, and icon can be edited.</p>
        )}
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold rounded-xl transition-colors"
      >
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  );
}
