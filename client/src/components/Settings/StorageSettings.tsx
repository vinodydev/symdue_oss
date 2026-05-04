/**
 * Storage Settings component - displays list of storage configurations
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { StorageConfig } from '@/types';
import { Plus, Trash2, Edit2, Database, HardDrive, Cloud, FileText, CheckCircle2, XCircle } from 'lucide-react';
import { StorageForm } from './StorageForm';
import { cn } from '@/utils/cn';

const STORAGE_TYPE_ICONS: Record<StorageConfig['storage_type'], React.ComponentType<{ size?: number; className?: string }>> = {
  postgresql: Database,
  redis: HardDrive,
  mongodb: Database,
  chroma: Cloud,
  local_file: FileText,
  minio: Cloud,
  s3: Cloud,
};

const STORAGE_TYPE_LABELS: Record<StorageConfig['storage_type'], string> = {
  postgresql: 'PostgreSQL',
  redis: 'Redis',
  mongodb: 'MongoDB',
  chroma: 'Chroma',
  local_file: 'Local File',
  minio: 'MinIO',
  s3: 'S3',
};

export function StorageSettings() {
  const [storages, setStorages] = useState<StorageConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingStorage, setEditingStorage] = useState<StorageConfig | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    loadStorages();
  }, []);

  const loadStorages = async () => {
    try {
      setLoading(true);
      const data = await api.getStorageConfigs();
      setStorages(data);
    } catch (error) {
      console.error('Failed to load storages:', error);
      alert('Failed to load storage configurations');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingStorage(null);
    setShowForm(true);
  };

  const handleEdit = (storage: StorageConfig) => {
    setEditingStorage(storage);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this storage configuration?')) {
      return;
    }

    try {
      await api.deleteStorageConfig(id);
      await loadStorages();
    } catch (error) {
      console.error('Failed to delete storage:', error);
      alert('Failed to delete storage configuration');
    }
  };

  const handleSave = async (data: any) => {
    try {
      if (editingStorage) {
        await api.updateStorageConfig(editingStorage.id, data);
      } else {
        await api.createStorageConfig(data);
      }
      setShowForm(false);
      setEditingStorage(null);
      await loadStorages();
    } catch (error) {
      console.error('Failed to save storage:', error);
      throw error; // Let form handle the error
    }
  };

  if (showForm) {
    return (
      <StorageForm
        storage={editingStorage}
        onSave={handleSave}
        onCancel={() => {
          setShowForm(false);
          setEditingStorage(null);
        }}
      />
    );
  }

  return (
    <div className="max-w-4xl">
      {/* Header - fixed */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-6 mb-8">
        <div>
          <h2 className="text-xl font-bold text-white">Storage Configurations</h2>
          <p className="text-slate-500 text-sm mt-1">
            Configure storage backends for Python nodes (PostgreSQL, Redis, MongoDB, Chroma, LocalFile, MinIO).
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-2xl shadow-xl transition-all"
        >
          <Plus size={20} /> Add Storage
        </button>
      </div>

      {/* Scrollable list */}
      <div className="overflow-y-auto custom-scrollbar h-[80vh]">
        {loading ? (
          <div className="text-center py-12 text-slate-600 italic text-sm">
            Loading storage configurations...
          </div>
        ) : storages.length === 0 ? (
          <div className="text-center py-12 text-slate-600 italic text-sm">
            No storage configurations yet. Click "Add Storage" to create one.
          </div>
        ) : (
          <div className="grid gap-6">
            {storages.map((storage) => {
              const Icon = STORAGE_TYPE_ICONS[storage.storage_type];
              return (
                <div
                  key={storage.id}
                  className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-10 relative group shadow-2xl transition-all hover:border-slate-700"
                >
                  <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-indigo-600/10 rounded-xl border border-indigo-500/20">
                        <Icon size={24} className="text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-white mb-1">{storage.name}</h3>
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                            {STORAGE_TYPE_LABELS[storage.storage_type]}
                          </span>
                          {storage.enabled ? (
                            <span className="flex items-center gap-1 text-xs text-emerald-400">
                              <CheckCircle2 size={12} />
                              Enabled
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-xs text-slate-500">
                              <XCircle size={12} />
                              Disabled
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEdit(storage)}
                        className="p-2 text-slate-500 hover:text-indigo-400 transition-colors"
                        title="Edit"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(storage.id)}
                        className="p-2 text-slate-500 hover:text-red-500 transition-colors"
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>

                  {/* Config preview */}
                  <div className="mt-4 p-4 bg-slate-950 rounded-xl border border-slate-800">
                    <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">
                      Configuration
                    </div>
                    <pre className="text-xs text-slate-400 font-mono overflow-x-auto">
                      {JSON.stringify(storage.config, null, 2)}
                    </pre>
                  </div>

                  {/* Metadata */}
                  <div className="mt-4 flex items-center gap-4 text-xs text-slate-600">
                    <span>ID: {storage.id.slice(0, 8)}...</span>
                    <span>Created: {new Date(storage.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

