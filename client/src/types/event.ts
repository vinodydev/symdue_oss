/**
 * Event types
 */

export type EventType = 'interval' | 'cron' | 'webhook' | 'queue';

export interface Event {
  id: string;
  name: string;
  type: EventType;
  schedule?: string | null;
  script: string;
  state?: Record<string, any> | null;
  enabled: boolean;
  queue_name?: string | null;
  webhook_secret?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  name: string;
  type: EventType;
  schedule?: string;
  script?: string;
  state?: Record<string, any>;
  enabled?: boolean;
  queue_name?: string;
  webhook_secret?: string;
}

export interface EventUpdate {
  name?: string;
  type?: EventType;
  schedule?: string;
  script?: string;
  state?: Record<string, any>;
  enabled?: boolean;
  queue_name?: string;
  webhook_secret?: string;
}

export interface EventInvocation {
  id: string;
  event_id: string;
  triggered_by?: string | null;
  input?: Record<string, any> | null;
  state_before?: Record<string, any> | null;
  state_after?: Record<string, any> | null;
  runtime_calls?: Array<{ method: string; args: any; result: any }> | null;
  error?: string | null;
  duration_ms?: number | null;
  started_at: string;
  completed_at?: string | null;
}

export interface EventInvocationDetail extends EventInvocation {
  log_output?: string | null;
  traceback?: string | null;
}
