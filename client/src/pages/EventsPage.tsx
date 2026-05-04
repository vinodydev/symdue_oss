/**
 * Events management page.
 */
import React, { useState, useEffect } from 'react';
import { Plus, Play, Pencil, Trash2, ToggleLeft, ToggleRight, List, Loader2, Zap, CheckCircle2 } from 'lucide-react';
import { api } from '@/services/api';
import type { FlowEvent } from '@/types';
import { EventFormPanel } from '@/components/Events/EventFormPanel';
import { EventInvocationsPanel } from '@/components/Events/EventInvocationsPanel';
import { cn } from '@/utils/cn';

const TYPE_COLORS: Record<string, string> = {
  interval: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  cron: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  webhook: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  queue: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
};

export function EventsPage() {
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [formEvent, setFormEvent] = useState<FlowEvent | null | undefined>(undefined); // undefined = closed
  const [invocationsEvent, setInvocationsEvent] = useState<FlowEvent | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [triggerSuccess, setTriggerSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getEvents();
      setEvents(data);
    } catch (err) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaved = (saved: FlowEvent) => {
    setEvents((prev) => {
      const idx = prev.findIndex((e) => e.id === saved.id);
      if (idx >= 0) {
        return prev.map((e) => (e.id === saved.id ? saved : e));
      }
      return [saved, ...prev];
    });
    setFormEvent(undefined);
  };

  const handleDelete = async (event: FlowEvent) => {
    if (!confirm(`Delete event "${event.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteEvent(event.id);
      setEvents((prev) => prev.filter((e) => e.id !== event.id));
    } catch (err) {
      console.error('Failed to delete event:', err);
      alert('Failed to delete event');
    }
  };

  const handleToggleEnabled = async (event: FlowEvent) => {
    try {
      const updated = event.enabled
        ? await api.disableEvent(event.id)
        : await api.enableEvent(event.id);
      setEvents((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
    } catch (err) {
      console.error('Failed to toggle event:', err);
    }
  };

  const handleTrigger = async (event: FlowEvent) => {
    setTriggeringId(event.id);
    try {
      await api.triggerEvent(event.id, {});
      setTriggerSuccess(event.id);
      setTimeout(() => setTriggerSuccess(null), 2000);
    } catch (err) {
      console.error('Failed to trigger event:', err);
      alert('Failed to trigger event');
    } finally {
      setTriggeringId(null);
    }
  };

  const formatDate = (s?: string | null) => {
    if (!s) return '—';
    return new Date(s).toLocaleString();
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden">
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Zap size={20} className="text-purple-400" />
          <h1 className="text-lg font-bold text-slate-100">Events</h1>
          <span className="text-xs text-slate-500 bg-slate-800 rounded-full px-2 py-0.5">
            {events.length}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setFormEvent(null)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} />
          New Event
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="text-slate-500 animate-spin" />
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <Zap size={40} className="text-slate-700 mb-4" />
            <h2 className="text-lg font-semibold text-slate-400 mb-2">No events yet</h2>
            <p className="text-sm text-slate-600 mb-6 max-w-sm">
              Events are standalone scheduled scripts that can emit signals to workflows, start runs, and manage their own state.
            </p>
            <button
              type="button"
              onClick={() => setFormEvent(null)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Plus size={16} />
              Create your first event
            </button>
          </div>
        ) : (
          <div className="border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Name</th>
                  <th className="text-left px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Type</th>
                  <th className="text-left px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Schedule</th>
                  <th className="text-left px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Enabled</th>
                  <th className="text-left px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Last Run</th>
                  <th className="text-right px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest">Actions</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr
                    key={event.id}
                    className="border-b border-slate-800/50 hover:bg-slate-900/40 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setFormEvent(event)}
                        className="text-sm text-slate-200 hover:text-purple-300 transition-colors font-medium"
                      >
                        {event.name}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full border capitalize', TYPE_COLORS[event.type] || 'text-slate-400 bg-slate-800 border-slate-700')}>
                        {event.type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500 font-mono">{event.schedule || '—'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => handleToggleEnabled(event)}
                        className={cn('transition-colors', event.enabled ? 'text-emerald-400 hover:text-emerald-300' : 'text-slate-600 hover:text-slate-400')}
                        title={event.enabled ? 'Disable' : 'Enable'}
                      >
                        {event.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500">{formatDate(event.last_run_at)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {/* Trigger */}
                        <button
                          type="button"
                          onClick={() => handleTrigger(event)}
                          disabled={triggeringId === event.id}
                          className="p-1.5 text-slate-500 hover:text-emerald-400 rounded-lg hover:bg-slate-800 transition-colors disabled:opacity-50"
                          title="Trigger now"
                        >
                          {triggeringId === event.id ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : triggerSuccess === event.id ? (
                            <CheckCircle2 size={14} className="text-emerald-400" />
                          ) : (
                            <Play size={14} />
                          )}
                        </button>
                        {/* Invocations */}
                        <button
                          type="button"
                          onClick={() => setInvocationsEvent(event)}
                          className="p-1.5 text-slate-500 hover:text-blue-400 rounded-lg hover:bg-slate-800 transition-colors"
                          title="View invocations"
                        >
                          <List size={14} />
                        </button>
                        {/* Edit */}
                        <button
                          type="button"
                          onClick={() => setFormEvent(event)}
                          className="p-1.5 text-slate-500 hover:text-amber-400 rounded-lg hover:bg-slate-800 transition-colors"
                          title="Edit"
                        >
                          <Pencil size={14} />
                        </button>
                        {/* Delete */}
                        <button
                          type="button"
                          onClick={() => handleDelete(event)}
                          className="p-1.5 text-slate-500 hover:text-red-400 rounded-lg hover:bg-slate-800 transition-colors"
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Form panel */}
      {formEvent !== undefined && (
        <EventFormPanel
          event={formEvent}
          onClose={() => setFormEvent(undefined)}
          onSaved={handleSaved}
        />
      )}

      {/* Invocations panel */}
      {invocationsEvent && (
        <EventInvocationsPanel
          event={invocationsEvent}
          onClose={() => setInvocationsEvent(null)}
        />
      )}
    </div>
  );
}
