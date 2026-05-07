// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Dialog for saving a workflow as a reusable template
 */
import React, { useState, useEffect } from 'react';
import { api } from '@/services/api';
import type { SaveWorkflowAsTemplateRequest } from '@/types';
import { X, Save, Loader2, Database, Code, Cpu } from 'lucide-react';
import { cn } from '@/utils/cn';

interface SaveWorkflowAsTemplateDialogProps {
  open: boolean;
  workflowId: string;
  workflowName: string;
  onClose: () => void;
  onSuccess: (templateId: string) => void;
}

export function SaveWorkflowAsTemplateDialog({
  open,
  workflowId,
  workflowName,
  onClose,
  onSuccess,
}: SaveWorkflowAsTemplateDialogProps) {
  const [templateName, setTemplateName] = useState(workflowName);
  const [templateDescription, setTemplateDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{
    workflow_env_vars: string[];
    input_ports: any[];
    output_ports: any[];
    storage_requirements?: Record<string, any>;
  } | null>(null);

  useEffect(() => {
    if (open) {
      setTemplateName(workflowName);
      setTemplateDescription('');
      setIsPublic(false);
      setPreview(null);
      setError(null);
    }
  }, [open, workflowName]);

  const handleSave = async () => {
    if (!templateName.trim()) {
      setError('Template name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: SaveWorkflowAsTemplateRequest = {
        template_name: templateName,
        template_description: templateDescription || undefined,
        is_public: isPublic,
      };

      const result = await api.saveWorkflowAsTemplate(workflowId, request);
      setPreview(result);
      
      // Show success and close after a moment
      setTimeout(() => {
        onSuccess(result.node_type_id);
        onClose();
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">Save Workflow as Template</h2>
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
              Template Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter template name"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description
            </label>
            <textarea
              value={templateDescription}
              onChange={(e) => setTemplateDescription(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              placeholder="Describe what this workflow template does..."
              rows={3}
              disabled={loading}
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="isPublic"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-slate-800 border-slate-700 rounded focus:ring-blue-500"
              disabled={loading}
            />
            <label htmlFor="isPublic" className="text-sm text-slate-300">
              Make this template public (others can use it)
            </label>
          </div>

          {preview && (
            <div className="mt-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Template Preview</h3>
              
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-slate-400 mb-1">
                    Environment Variables ({preview.workflow_env_vars.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {preview.workflow_env_vars.map((envVar) => (
                      <span
                        key={envVar}
                        className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded"
                      >
                        {envVar}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-slate-400 mb-1">
                    Input Ports ({preview.input_ports.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {preview.input_ports.map((port, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-blue-500/20 text-blue-300 text-xs rounded"
                      >
                        {port.node_name}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-slate-400 mb-1">
                    Output Ports ({preview.output_ports.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {preview.output_ports.map((port, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-green-500/20 text-green-300 text-xs rounded"
                      >
                        {port.node_name}
                      </span>
                    ))}
                  </div>
                </div>

                {preview.storage_requirements && Object.keys(preview.storage_requirements).length > 0 && (
                  <div>
                    <p className="text-xs text-slate-400 mb-1">
                      Storage Requirements
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(preview.storage_requirements).map((type) => (
                        <span
                          key={type}
                          className="px-2 py-1 bg-purple-500/20 text-purple-300 text-xs rounded"
                        >
                          {type}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
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
            onClick={handleSave}
            disabled={loading || !templateName.trim()}
            className={cn(
              "px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2",
              loading || !templateName.trim()
                ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            )}
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save size={16} />
                Save Template
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

