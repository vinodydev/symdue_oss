/**
 * Dialog for creating a node from a template
 */
import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { api } from '@/services/api';
import type { CreateNodeFromTemplateRequest, NodeType, StorageConfig } from '@/types';
import { X, Plus, Loader2, Database, Trash2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import { StorageSelectorModal } from '../Properties/StorageSelectorModal';

interface CreateNodeFromTemplateDialogProps {
  open: boolean;
  template: NodeType;
  workspaceId: string;
  onClose: () => void;
  onSuccess: (nodeId: string) => void;
}

export function CreateNodeFromTemplateDialog({
  open,
  template,
  workspaceId,
  onClose,
  onSuccess,
}: CreateNodeFromTemplateDialogProps) {
  const [nodeName, setNodeName] = useState(template.name || '');
  const [workflowEnv, setWorkflowEnv] = useState<Record<string, string>>({});
  const [nodeEnv, setNodeEnv] = useState<Record<string, string>>({});
  const [storages, setStorages] = useState<Array<{alias: string, storage_id: string, name?: string}>>([]);
  const [requirements, setRequirements] = useState('');
  const [availableStorages, setAvailableStorages] = useState<StorageConfig[]>([]);
  const [showStorageSelector, setShowStorageSelector] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && template) {
      setNodeName(template.name || '');
      
      // Initialize env vars with defaults from template
      const workflowTemplate = template.workflow_env_template || {};
      const nodeTemplate = template.node_env_template || {};
      
      const defaultWorkflowEnv: Record<string, string> = {};
      const defaultNodeEnv: Record<string, string> = {};
      
      Object.entries(workflowTemplate).forEach(([key, schema]: [string, any]) => {
        if (schema.default) {
          defaultWorkflowEnv[key] = schema.default;
        }
      });
      
      Object.entries(nodeTemplate).forEach(([key, schema]: [string, any]) => {
        if (schema.default) {
          defaultNodeEnv[key] = schema.default;
        }
      });
      
      setWorkflowEnv(defaultWorkflowEnv);
      setNodeEnv(defaultNodeEnv);
      
      // Restore storages from template
      const templateData = template.node_template_data || {};
      const originalConfig = templateData.original_config || {};
      if (originalConfig.storages && Array.isArray(originalConfig.storages)) {
        setStorages(originalConfig.storages.map((s: any) => ({
          alias: s.alias || s.name || 'default',
          storage_id: s.storage_id || s.id,
          name: s.name
        })));
      }
      
      // Restore requirements
      if (originalConfig.requirements) {
        setRequirements(originalConfig.requirements);
      }
      
      // Load available storages
      loadStorages();
    }
  }, [open, template]);

  const loadStorages = async () => {
    try {
      const storageConfigs = await api.getStorageConfigs();
      setAvailableStorages(storageConfigs.filter(s => s.enabled));
    } catch (err) {
      console.error('Failed to load storages:', err);
    }
  };

  const handleAttachStorage = async (storageId: string, alias: string) => {
    const storage = availableStorages.find(s => s.id === storageId);
    if (storage) {
      setStorages([...storages, { alias, storage_id: storageId, name: storage.name }]);
      setShowStorageSelector(false);
    }
  };

  const handleRemoveStorage = (index: number) => {
    setStorages(storages.filter((_, i) => i !== index));
  };

  const handleCreate = async () => {
    if (!nodeName.trim()) {
      setError('Node name is required');
      return;
    }

    // Validate required env vars
    const workflowTemplate = template.workflow_env_template || {};
    const required = Object.entries(workflowTemplate)
      .filter(([_, schema]: [string, any]) => schema.required)
      .map(([key]) => key);
    
    const missing = required.filter(key => !workflowEnv[key]?.trim());
    if (missing.length > 0) {
      setError(`Missing required environment variables: ${missing.join(', ')}`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: CreateNodeFromTemplateRequest = {
        template_id: template.id,
        node_name: nodeName,
        workflow_env: Object.keys(workflowEnv).length > 0 ? workflowEnv : undefined,
        node_env: Object.keys(nodeEnv).length > 0 ? nodeEnv : undefined,
        storages: storages.length > 0 ? storages.map(s => ({ alias: s.alias, storage_id: s.storage_id })) : undefined,
        requirements: requirements.trim() || undefined,
      };

      const node = await api.createNodeFromTemplate(workspaceId, request);
      onSuccess(node.id);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create node');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  const workflowTemplate = template.workflow_env_template || {};
  const nodeTemplate = template.node_env_template || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Create Node from Template</h2>
            <p className="text-sm text-slate-400 mt-1">{template.description || template.name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors"
            disabled={loading}
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Node Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={nodeName}
              onChange={(e) => setNodeName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter node name"
              disabled={loading}
            />
          </div>

          {Object.keys(workflowTemplate).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Workflow Environment Variables</h3>
              <div className="space-y-2">
                {Object.entries(workflowTemplate).map(([key, schema]: [string, any]) => (
                  <div key={key}>
                    <label className="block text-xs text-slate-400 mb-1">
                      {schema.title || key}
                      {schema.required && <span className="text-red-400 ml-1">*</span>}
                    </label>
                    <input
                      type="text"
                      value={workflowEnv[key] || ''}
                      onChange={(e) => setWorkflowEnv({ ...workflowEnv, [key]: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                      placeholder={schema.description || key}
                      disabled={loading}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {Object.keys(nodeTemplate).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Node Environment Variables</h3>
              <div className="space-y-2">
                {Object.entries(nodeTemplate).map(([key, schema]: [string, any]) => (
                  <div key={key}>
                    <label className="block text-xs text-slate-400 mb-1">
                      {schema.title || key}
                    </label>
                    <input
                      type="text"
                      value={nodeEnv[key] || ''}
                      onChange={(e) => setNodeEnv({ ...nodeEnv, [key]: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                      placeholder={schema.description || key}
                      disabled={loading}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Requirements field (for Python nodes) */}
          {template.node_template_data?.original_node_type_id === 'custom-python' && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Requirements
              </label>
              <textarea
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm resize-none"
                placeholder="pip requirements (e.g., playwright, requests)"
                rows={3}
                disabled={loading}
              />
              <p className="text-xs text-slate-500 mt-1">
                Python packages required for this node to run
              </p>
            </div>
          )}

          {/* Storage Configuration */}
          {template.node_template_data?.original_config?.storages && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Storage Configuration
              </label>
              <div className="space-y-2">
                {storages.length > 0 && (
                  <div className="space-y-2">
                    {storages.map((storage, index) => {
                      const storageInfo = availableStorages.find(s => s.id === storage.storage_id);
                      return (
                        <div key={index} className="flex items-center gap-2 p-2 bg-slate-800 border border-slate-700 rounded-lg">
                          <Database size={16} className="text-slate-400 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-slate-200 truncate">
                              {storageInfo?.name || storage.name || 'Unknown Storage'}
                            </div>
                            <div className="text-xs text-slate-400">
                              Alias: <span className="font-mono">{storage.alias}</span>
                            </div>
                          </div>
                          <button
                            onClick={() => handleRemoveStorage(index)}
                            className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                            disabled={loading}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
                <button
                  onClick={() => setShowStorageSelector(true)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors text-sm flex items-center justify-center gap-2"
                  disabled={loading}
                >
                  <Database size={16} />
                  {storages.length > 0 ? 'Add Another Storage' : 'Attach Storage'}
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-slate-300 hover:text-slate-100 transition-colors"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={loading || !nodeName.trim()}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2",
              loading || !nodeName.trim()
                ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            )}
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus size={16} />
                Create Node
              </>
            )}
          </button>
        </div>
      </div>

      {showStorageSelector && createPortal(
        <StorageSelectorModal
          availableStorages={availableStorages}
          onSelect={handleAttachStorage}
          onClose={() => setShowStorageSelector(false)}
        />,
        document.body
      )}
    </div>
  );
}

