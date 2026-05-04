/**
 * Dialog for creating a workflow from a template
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { CreateWorkflowFromTemplateRequest, NodeType, StorageConfig } from '@/types';
import { X, Plus, Loader2, Database } from 'lucide-react';
import { cn } from '@/utils/cn';

interface CreateWorkflowFromTemplateDialogProps {
  open: boolean;
  template: NodeType;
  onClose: () => void;
  onSuccess: (workflowId: string) => void;
}

export function CreateWorkflowFromTemplateDialog({
  open,
  template,
  onClose,
  onSuccess,
}: CreateWorkflowFromTemplateDialogProps) {
  const [workflowName, setWorkflowName] = useState(template.name || '');
  const [workflowEnv, setWorkflowEnv] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableStorages, setAvailableStorages] = useState<StorageConfig[]>([]);
  const [storageMapping, setStorageMapping] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open && template) {
      setWorkflowName(template.name || '');
      
      // Initialize env vars with defaults
      const workflowTemplate = template.workflow_env_template || {};
      const defaultWorkflowEnv: Record<string, string> = {};
      
      Object.entries(workflowTemplate).forEach(([key, schema]: [string, any]) => {
        if (schema.default) {
          defaultWorkflowEnv[key] = schema.default;
        }
      });
      
      setWorkflowEnv(defaultWorkflowEnv);
      
      // Load available storages
      loadStorages();
    }
  }, [open, template]);

  const loadStorages = async () => {
    try {
      const storages = await api.getStorageConfigs();
      setAvailableStorages(storages);
      
      // Auto-select storages if single match
      const storageRequirements = template.workflow_template_data?.storage_requirements || {};
      const autoMapping: Record<string, string> = {};
      
      Object.keys(storageRequirements).forEach((storageType) => {
        const matching = storages.filter(s => s.storage_type === storageType && s.enabled);
        if (matching.length === 1) {
          autoMapping[storageType] = matching[0].name;
        }
      });
      
      setStorageMapping(autoMapping);
    } catch (err) {
      console.error('Failed to load storages:', err);
    }
  };

  const handleCreate = async () => {
    if (!workflowName.trim()) {
      setError('Workflow name is required');
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
      const request: CreateWorkflowFromTemplateRequest = {
        template_id: template.id,
        workflow_name: workflowName,
        workflow_env: Object.keys(workflowEnv).length > 0 ? workflowEnv : undefined,
      };

      const workflow = await api.createWorkflowFromTemplate(request);
      onSuccess(workflow.id);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create workflow');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  const workflowTemplate = template.workflow_env_template || {};
  const storageRequirements = template.workflow_template_data?.storage_requirements || {};
  const inputPorts = template.input_ports || [];
  const outputPorts = template.output_ports || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">Create Workflow from Template</h2>
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
              Workflow Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={workflowName}
              onChange={(e) => setWorkflowName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter workflow name"
              disabled={loading}
            />
          </div>

          {Object.keys(workflowTemplate).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Environment Variables</h3>
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

          {Object.keys(storageRequirements).length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Storage Requirements</h3>
              <div className="space-y-2">
                {Object.entries(storageRequirements).map(([storageType, requirement]: [string, any]) => {
                  const matchingStorages = availableStorages.filter(
                    s => s.storage_type === storageType && s.enabled
                  );
                  
                  return (
                    <div key={storageType} className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
                      <div className="flex items-center gap-2 mb-2">
                        <Database size={16} className="text-slate-400" />
                        <span className="text-sm font-medium text-slate-200">{storageType}</span>
                        {requirement.required && (
                          <span className="text-xs text-red-400">Required</span>
                        )}
                      </div>
                      {requirement.description && (
                        <p className="text-xs text-slate-400 mb-2">{requirement.description}</p>
                      )}
                      {matchingStorages.length > 0 ? (
                        <select
                          value={storageMapping[storageType] || ''}
                          onChange={(e) => setStorageMapping({ ...storageMapping, [storageType]: e.target.value })}
                          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                          disabled={loading}
                        >
                          <option value="">Select storage...</option>
                          {matchingStorages.map((storage) => (
                            <option key={storage.id} value={storage.name}>
                              {storage.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <p className="text-xs text-yellow-400">
                          No {storageType} storage found. Create one in Settings.
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {inputPorts.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-2">
                Input Ports ({inputPorts.length})
              </h3>
              <p className="text-xs text-slate-400">
                These nodes will be available as inputs when using this workflow as a sub-workflow.
              </p>
            </div>
          )}

          {outputPorts.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-200 mb-2">
                Output Ports ({outputPorts.length})
              </h3>
              <p className="text-xs text-slate-400">
                These nodes will provide outputs when using this workflow as a sub-workflow.
              </p>
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
            disabled={loading || !workflowName.trim()}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2",
              loading || !workflowName.trim()
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
                Create Workflow
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

