// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Storage Selector Modal - for attaching storages to nodes
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { StorageConfig } from '@/types';
import { X, Database, HardDrive, Cloud, FileText } from 'lucide-react';
import { cn } from '@/utils/cn';

interface StorageSelectorModalProps {
  availableStorages: StorageConfig[];
  onSelect: (storageId: string, alias: string) => void;
  onClose: () => void;
}

const STORAGE_TYPE_ICONS: Record<StorageConfig['storage_type'], React.ComponentType<{ size?: number; className?: string }>> = {
  postgresql: Database,
  redis: HardDrive,
  mongodb: Database,
  chroma: Cloud,
  local_file: FileText,
  minio: Cloud,
  s3: Cloud,
};

export function StorageSelectorModal({
  availableStorages,
  onSelect,
  onClose,
}: StorageSelectorModalProps) {
  const [selectedStorageId, setSelectedStorageId] = useState<string>('');
  const [alias, setAlias] = useState<string>('');

  const selectedStorage = availableStorages.find((s) => s.id === selectedStorageId);
  const Icon = selectedStorage ? STORAGE_TYPE_ICONS[selectedStorage.storage_type] : null;

  const handleSelect = () => {
    console.log('handleSelect called', { selectedStorageId, alias });
    if (!selectedStorageId) {
      alert('Please select a storage');
      return;
    }
    console.log('Calling onSelect', { selectedStorageId, alias: alias.trim() || '' });
    onSelect(selectedStorageId, alias.trim() || '');
  };

  // Auto-generate alias from storage name when storage is selected
  useEffect(() => {
    if (selectedStorage && !alias) {
      const generatedAlias = selectedStorage.name
        .toLowerCase()
        .replace(/\s+/g, '_')
        .replace(/[^a-z0-9_]/g, '');
      setAlias(generatedAlias);
    }
  }, [selectedStorageId, selectedStorage, alias]);

  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={(e) => {
        // Close modal when clicking backdrop
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div 
        className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-8 max-w-2xl w-full shadow-2xl animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-white">Attach Storage to Node</h3>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          {/* Storage Selection */}
          <div>
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-2">
              Select Storage
            </label>
            <select
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white outline-none focus:border-indigo-500 appearance-none"
              value={selectedStorageId}
              onChange={(e) => setSelectedStorageId(e.target.value)}
            >
              <option value="">Choose a storage...</option>
              {availableStorages
                .filter((s) => s.enabled)
                .map((storage) => {
                  const StorageIcon = STORAGE_TYPE_ICONS[storage.storage_type];
                  return (
                    <option key={storage.id} value={storage.id}>
                      {storage.name} ({storage.storage_type})
                    </option>
                  );
                })}
            </select>
          </div>

          {/* Selected Storage Info */}
          {selectedStorage && (
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                {Icon && <Icon size={20} className="text-indigo-400" />}
                <div>
                  <div className="text-sm font-bold text-white">{selectedStorage.name}</div>
                  <div className="text-xs text-slate-500 uppercase">{selectedStorage.storage_type}</div>
                </div>
              </div>
              {selectedStorage.config && (
                <div className="mt-3 text-xs text-slate-400">
                  <div className="font-bold text-slate-500 mb-1">Configuration:</div>
                  <pre className="font-mono overflow-x-auto">
                    {JSON.stringify(selectedStorage.config, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Alias Input */}
          <div>
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-2">
              Alias (optional)
              <span className="text-slate-600 normal-case font-normal ml-1">
                - Used as parameter name in Python: storages["alias"]
              </span>
            </label>
            <input
              type="text"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm text-white font-mono outline-none focus:border-indigo-500"
              value={alias}
              onChange={(e) => {
                // Only allow lowercase, numbers, underscores
                const value = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
                setAlias(value);
              }}
              placeholder="e.g., main_db, file_storage, cache"
            />
            <div className="text-xs text-slate-600 mt-1">
              If not provided, will use storage name (lowercase, spaces to underscores)
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-slate-800">
            <button
              onClick={handleSelect}
              disabled={!selectedStorageId}
              className={cn(
                "flex-1 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl transition-all",
                !selectedStorageId && "opacity-50 cursor-not-allowed"
              )}
            >
              Attach Storage
            </button>
            <button
              onClick={onClose}
              className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

