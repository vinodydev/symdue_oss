/**
 * Dialog for saving a node as a reusable template
 */
import React, { useState } from 'react';
import { api } from '@/services/api';
import type { SaveNodeAsTemplateRequest } from '@/types';
import { X, Save, Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';

interface SaveNodeAsTemplateDialogProps {
  open: boolean;
  nodeId: string;
  nodeName: string;
  onClose: () => void;
  onSuccess: (templateId: string) => void;
}

export function SaveNodeAsTemplateDialog({
  open,
  nodeId,
  nodeName,
  onClose,
  onSuccess,
}: SaveNodeAsTemplateDialogProps) {
  const [templateName, setTemplateName] = useState(nodeName);
  const [templateDescription, setTemplateDescription] = useState('');
  const [isPublic, setIsPublic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSave = async () => {
    if (!templateName.trim()) {
      setError('Template name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: SaveNodeAsTemplateRequest = {
        template_name: templateName,
        template_description: templateDescription || undefined,
        is_public: isPublic,
      };

      const result = await api.saveNodeAsTemplate(nodeId, request);
      onSuccess(result.node_type_id);
      onClose();
      
      // Reset form
      setTemplateName(nodeName);
      setTemplateDescription('');
      setIsPublic(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-slate-900 rounded-xl border border-slate-700 w-full max-w-md p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-100">Save Node as Template</h2>
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
              placeholder="Describe what this template does..."
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

