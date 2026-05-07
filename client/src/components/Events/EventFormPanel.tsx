// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Side panel for creating / editing Events.
 */
import React, { useState, useEffect } from 'react';
import { X, Save, Loader2 } from 'lucide-react';
import { api } from '@/services/api';
import type { FlowEvent, EventCreate, EventUpdate, EventType } from '@/types';
import { ScriptEditor } from './ScriptEditor';

interface EventFormPanelProps {
  event?: FlowEvent | null;
  onClose: () => void;
  onSaved: (event: FlowEvent) => void;
}

const EVENT_TYPES: { value: EventType; label: string; description: string }[] = [
  { value: 'interval', label: 'Interval', description: 'Runs every N minutes/hours' },
  { value: 'cron', label: 'Cron', description: 'Runs on a cron schedule' },
  { value: 'webhook', label: 'Webhook', description: 'Runs when called via HTTP' },
  { value: 'queue', label: 'Queue', description: 'Runs when message arrives on a queue' },
];

export function EventFormPanel({ event, onClose, onSaved }: EventFormPanelProps) {
  const isEditing = !!event;

  const [name, setName] = useState(event?.name || '');
  const [type, setType] = useState<EventType>(event?.type || 'interval');
  const [schedule, setSchedule] = useState(event?.schedule || '');
  const [script, setScript] = useState(event?.script || '');
  const [enabled, setEnabled] = useState(event?.enabled ?? true);
  const [queueName, setQueueName] = useState(event?.queue_name || '');
  const [webhookSecret, setWebhookSecret] = useState(event?.webhook_secret || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (event) {
      setName(event.name);
      setType(event.type);
      setSchedule(event.schedule || '');
      setScript(event.script || '');
      setEnabled(event.enabled);
      setQueueName(event.queue_name || '');
      setWebhookSecret(event.webhook_secret || '');
    }
  }, [event?.id]);

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      let saved: FlowEvent;
      if (isEditing && event) {
        const update: EventUpdate = {
          name,
          type,
          schedule: schedule || undefined,
          script,
          enabled,
          queue_name: queueName || undefined,
          webhook_secret: webhookSecret || undefined,
        };
        saved = await api.updateEvent(event.id, update);
      } else {
        const create: EventCreate = {
          name,
          type,
          schedule: schedule || undefined,
          script,
          enabled,
          queue_name: queueName || undefined,
          webhook_secret: webhookSecret || undefined,
        };
        saved = await api.createEvent(create);
      }
      onSaved(saved);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to save event');
    } finally {
      setSaving(false);
    }
  };

  const showSchedule = type === 'interval' || type === 'cron';
  const showQueueName = type === 'queue';
  const showWebhookSecret = type === 'webhook';

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-slate-900 border-l border-slate-800 flex flex-col z-50 shadow-2xl animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <h2 className="text-sm font-bold text-slate-200">
          {isEditing ? 'Edit Event' : 'New Event'}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-slate-500 hover:text-slate-300 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Name */}
        <div>
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
            Name
          </label>
          <input
            type="text"
            className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
            placeholder="My Event"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Type */}
        <div>
          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
            Type
          </label>
          <div className="grid grid-cols-2 gap-2">
            {EVENT_TYPES.map((et) => (
              <button
                key={et.value}
                type="button"
                onClick={() => setType(et.value)}
                className={[
                  'p-3 rounded-lg border text-left transition-all',
                  type === et.value
                    ? 'border-purple-500/60 bg-purple-500/10 text-purple-300'
                    : 'border-slate-700/50 bg-slate-800/40 text-slate-400 hover:border-slate-600',
                ].join(' ')}
              >
                <div className="text-xs font-bold">{et.label}</div>
                <div className="text-[10px] opacity-70 mt-0.5">{et.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Schedule (interval/cron) */}
        {showSchedule && (
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
              {type === 'interval' ? 'Interval' : 'Cron Expression'}
            </label>
            <input
              type="text"
              className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
              placeholder={type === 'interval' ? 'e.g. 5m, 1h, 30s' : 'e.g. 0 9 * * MON-FRI'}
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
            />
          </div>
        )}

        {/* Queue name */}
        {showQueueName && (
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
              Queue Name
            </label>
            <input
              type="text"
              className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
              placeholder="my_queue_stream"
              value={queueName}
              onChange={(e) => setQueueName(e.target.value)}
            />
          </div>
        )}

        {/* Webhook secret */}
        {showWebhookSecret && (
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
              Webhook Secret (optional)
            </label>
            <input
              type="text"
              className="w-full bg-slate-800/60 border border-slate-600/40 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/60"
              placeholder="HMAC secret for verification"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)}
            />
            {isEditing && event?.id && (
              <p className="text-[10px] text-slate-500 mt-1">
                Webhook URL: <code className="text-slate-400">/api/events/{event.id}/trigger</code>
              </p>
            )}
          </div>
        )}

        {/* Script */}
        <ScriptEditor value={script} onChange={setScript} minHeight="300px" />

        {/* Enabled */}
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="rounded border-slate-600 bg-slate-950 text-purple-500 focus:ring-purple-500"
          />
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-widest">
            Enabled
          </span>
        </label>
      </div>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {isEditing ? 'Save Changes' : 'Create Event'}
        </button>
      </div>
    </div>
  );
}
