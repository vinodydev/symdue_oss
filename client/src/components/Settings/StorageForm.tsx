// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Storage configuration form component
 * Supports all storage types: PostgreSQL, Redis, MongoDB, Chroma, LocalFile, MinIO
 */
import React, { useState, useEffect } from 'react';
import type { StorageConfig, CreateStorageConfigRequest, UpdateStorageConfigRequest } from '@/types';
import { Database, HardDrive, Cloud, FileText, X } from 'lucide-react';
import { cn } from '@/utils/cn';

interface StorageFormProps {
  storage?: StorageConfig | null;
  onSave: (data: CreateStorageConfigRequest | UpdateStorageConfigRequest) => Promise<void>;
  onCancel: () => void;
}

const STORAGE_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL', icon: Database, description: 'SQL database with pgvector support' },
  { value: 'redis', label: 'Redis', icon: HardDrive, description: 'In-memory cache' },
  { value: 'mongodb', label: 'MongoDB', icon: Database, description: 'Document database' },
  { value: 'chroma', label: 'Chroma', icon: Cloud, description: 'Vector database' },
  { value: 'local_file', label: 'Local File', icon: FileText, description: 'File system storage' },
  { value: 'minio', label: 'MinIO', icon: Cloud, description: 'S3-compatible storage' },
] as const;

export function StorageForm({ storage, onSave, onCancel }: StorageFormProps) {
  const [name, setName] = useState(storage?.name || '');
  const [storageType, setStorageType] = useState<StorageConfig['storage_type']>(
    storage?.storage_type || 'redis'
  );
  const [enabled, setEnabled] = useState(storage?.enabled ?? true);
  const [config, setConfig] = useState<Record<string, any>>(storage?.config || {});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (storage) {
      setName(storage.name);
      setStorageType(storage.storage_type);
      setEnabled(storage.enabled);
      setConfig(storage.config || {});
    } else {
      // Reset to defaults for new storage
      setName('');
      setStorageType('redis');
      setEnabled(true);
      setConfig({});
    }
  }, [storage]);

  const handleSave = async () => {
    if (!name.trim()) {
      alert('Storage name is required');
      return;
    }

    setSaving(true);
    try {
      if (storage) {
        await onSave({ name, config, enabled });
      } else {
        await onSave({ name, storage_type: storageType, config, enabled });
      }
    } catch (error) {
      console.error('Failed to save storage:', error);
      alert('Failed to save storage configuration');
    } finally {
      setSaving(false);
    }
  };

  const updateConfigField = (key: string, value: any) => {
    setConfig({ ...config, [key]: value });
  };

  // ─── Embedding function picker (issue14) ──────────────────────────
  // Used by vector backends (chroma, postgresql with pgvector) to enable
  // server-side auto-embedding of text queries. When set, nodes can call
  // storages["X"].search("plain text") without writing embedding code.
  const EMBEDDING_PRESETS: Array<{ value: string; label: string }> = [
    { value: '', label: '(none — caller must provide vectors)' },
    {
      value: 'sentence-transformers:BAAI/bge-small-en-v1.5',
      label: 'sentence-transformers:BAAI/bge-small-en-v1.5  (384d, fast, recommended)',
    },
    {
      value: 'sentence-transformers:BAAI/bge-base-en-v1.5',
      label: 'sentence-transformers:BAAI/bge-base-en-v1.5  (768d, higher quality)',
    },
    {
      value: 'sentence-transformers:all-MiniLM-L6-v2',
      label: 'sentence-transformers:all-MiniLM-L6-v2  (384d, legacy)',
    },
    { value: '__custom__', label: 'Custom...' },
  ];

  const renderEmbeddingFunctionField = () => {
    const current: string = config.embedding_function || '';
    const isPreset = EMBEDDING_PRESETS.some(
      (p) => p.value === current && p.value !== '__custom__',
    );
    const showCustom = current !== '' && !isPreset;
    const dropdownValue = showCustom ? '__custom__' : current;
    return (
      <div>
        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
          Embedding Function (optional)
        </label>
        <select
          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
          value={dropdownValue}
          onChange={(e) => {
            const v = e.target.value;
            if (v === '__custom__') {
              // Switch to custom mode: keep existing custom value, or seed empty
              if (!showCustom) updateConfigField('embedding_function', current || ' ');
            } else {
              updateConfigField('embedding_function', v || undefined);
            }
          }}
        >
          {EMBEDDING_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        {showCustom && (
          <input
            type="text"
            className="mt-2 w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
            value={current}
            onChange={(e) => updateConfigField('embedding_function', e.target.value)}
            placeholder="provider:model_id  (e.g. sentence-transformers:BAAI/bge-large-en-v1.5)"
          />
        )}
        <p className="mt-1 text-[11px] text-slate-500">
          When set, <code>storages["X"].search("text")</code> auto-embeds via the backend.
          Leave as <em>(none)</em> if your nodes pass pre-computed vectors.
        </p>
      </div>
    );
  };

  const renderStorageTypeFields = () => {
    switch (storageType) {
      case 'postgresql':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Connection String
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.connection_string || ''}
                onChange={(e) => updateConfigField('connection_string', e.target.value)}
                placeholder="postgres://user:password@postgres:5432/dbname"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Table Name
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.table || 'storage_data'}
                onChange={(e) => updateConfigField('table', e.target.value)}
                placeholder="storage_data"
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="enable_vector"
                checked={config.enable_vector !== false}
                onChange={(e) => updateConfigField('enable_vector', e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="enable_vector" className="text-sm text-slate-300">
                Enable vector search (pgvector)
              </label>
            </div>
            {config.enable_vector !== false && (
              <div>
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                  Embedding Dimension
                </label>
                <input
                  type="number"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                  value={config.embedding_dimension ?? 384}
                  onChange={(e) =>
                    updateConfigField(
                      'embedding_dimension',
                      parseInt(e.target.value, 10) || 384,
                    )
                  }
                  placeholder="384"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Must match your embedding model's output dimension. bge-small / MiniLM = 384, bge-base / mpnet = 768, OpenAI ada-002 = 1536.
                </p>
              </div>
            )}
            {config.enable_vector !== false && renderEmbeddingFunctionField()}
          </>
        );

      case 'redis':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Connection String
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.connection_string || ''}
                onChange={(e) => updateConfigField('connection_string', e.target.value)}
                placeholder="redis://redis:6379/0"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Key Prefix
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.key_prefix || ''}
                onChange={(e) => updateConfigField('key_prefix', e.target.value)}
                placeholder="memory:"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Default TTL (seconds, optional)
              </label>
              <input
                type="number"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.default_ttl || ''}
                onChange={(e) => updateConfigField('default_ttl', e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="3600"
              />
            </div>
          </>
        );

      case 'mongodb':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Connection String
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.connection_string || ''}
                onChange={(e) => updateConfigField('connection_string', e.target.value)}
                placeholder="mongodb://mongodb:27017/graphmind"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Database Name
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.database || 'graphmind'}
                onChange={(e) => updateConfigField('database', e.target.value)}
                placeholder="graphmind"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Collection Name
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.collection || 'memory'}
                onChange={(e) => updateConfigField('collection', e.target.value)}
                placeholder="memory"
              />
            </div>
          </>
        );

      case 'chroma':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Persist Directory
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.persist_directory || '/app/storage/chroma'}
                onChange={(e) => updateConfigField('persist_directory', e.target.value)}
                placeholder="/app/storage/chroma"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Collection Name
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.collection_name || 'memory'}
                onChange={(e) => updateConfigField('collection_name', e.target.value)}
                placeholder="memory"
              />
            </div>
            {renderEmbeddingFunctionField()}
          </>
        );

      case 'local_file':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Base Path
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.base_path || '/app/storage/files'}
                onChange={(e) => updateConfigField('base_path', e.target.value)}
                placeholder="/app/storage/files"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Base URL
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.base_url || 'http://localhost:8000/files'}
                onChange={(e) => updateConfigField('base_url', e.target.value)}
                placeholder="http://localhost:8000/files"
              />
            </div>
          </>
        );

      case 'minio':
        return (
          <>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Endpoint URL
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
                value={config.endpoint || ''}
                onChange={(e) => updateConfigField('endpoint', e.target.value)}
                placeholder="http://minio:9000"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Access Key
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.access_key || ''}
                onChange={(e) => updateConfigField('access_key', e.target.value)}
                placeholder="minioadmin"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Secret Key
              </label>
              <input
                type="password"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.secret_key || ''}
                onChange={(e) => updateConfigField('secret_key', e.target.value)}
                placeholder="minioadmin"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Bucket Name
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.bucket_name || 'graphmind-files'}
                onChange={(e) => updateConfigField('bucket_name', e.target.value)}
                placeholder="graphmind-files"
              />
            </div>
            <div>
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
                Region
              </label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
                value={config.region || 'us-east-1'}
                onChange={(e) => updateConfigField('region', e.target.value)}
                placeholder="us-east-1"
              />
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="use_ssl"
                checked={config.use_ssl === true}
                onChange={(e) => updateConfigField('use_ssl', e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="use_ssl" className="text-sm text-slate-300">
                Use SSL
              </label>
            </div>
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-10 space-y-6 shadow-2xl">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-bold text-white">
          {storage ? 'Edit Storage Configuration' : 'Create Storage Configuration'}
        </h3>
        <button
          onClick={onCancel}
          className="text-slate-500 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      <div className="space-y-6">
        {/* Name */}
        <div>
          <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
            Storage Name
          </label>
          <input
            type="text"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Storage"
          />
        </div>

        {/* Storage Type (only for new storage) */}
        {!storage && (
          <div>
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">
              Storage Type
            </label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500 appearance-none"
              value={storageType}
              onChange={(e) => {
                setStorageType(e.target.value as StorageConfig['storage_type']);
                setConfig({}); // Reset config when type changes
              }}
            >
              {STORAGE_TYPES.map((type) => {
                const Icon = type.icon;
                return (
                  <option key={type.value} value={type.value}>
                    {type.label} - {type.description}
                  </option>
                );
              })}
            </select>
          </div>
        )}

        {/* Type-specific fields */}
        <div className="space-y-4 pt-4 border-t border-slate-800">
          {renderStorageTypeFields()}
        </div>

        {/* Enabled toggle */}
        <div className="flex items-center gap-3 pt-4 border-t border-slate-800">
          <input
            type="checkbox"
            id="enabled"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500"
          />
          <label htmlFor="enabled" className="text-sm text-slate-300">
            Enabled
          </label>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className={cn(
              "flex-1 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl transition-all",
              (saving || !name.trim()) && "opacity-50 cursor-not-allowed"
            )}
          >
            {saving ? 'Saving...' : storage ? 'Update' : 'Create'}
          </button>
          <button
            onClick={onCancel}
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl transition-all"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

