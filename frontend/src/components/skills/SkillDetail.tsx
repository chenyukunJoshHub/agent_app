'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, BookOpen, Wrench, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Skill } from '@/types/skills';

interface SkillDetailProps {
  skill: Skill | null;
  isOpen: boolean;
  onClose: () => void;
}

export function SkillDetail({ skill, isOpen, onClose }: SkillDetailProps) {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load skill content when skill changes
  useEffect(() => {
    if (!skill || !isOpen) {
      setContent('');
      setError(null);
      return;
    }

    const loadContent = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // In a real implementation, you'd fetch from the backend
        // For now, we'll just show the metadata
        setContent(`# ${skill.name}\n\n${skill.description}\n\n**Tools:** ${skill.tools.join(', ') || 'None'}\n\n**File:** ${skill.file_path}`);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load skill content');
      } finally {
        setIsLoading(false);
      }
    };

    loadContent();
  }, [skill, isOpen]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 z-40"
            onClick={onClose}
            data-testid="skill-detail-backdrop"
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 h-full w-full max-w-lg bg-background-card shadow-xl z-50 flex flex-col"
            data-testid="skill-detail-drawer"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border p-6">
              <div>
                <h2 className="text-xl font-semibold text-text-primary">{skill?.name}</h2>
                <p className="text-sm text-muted-foreground mt-1">Skill Details</p>
              </div>
              <button
                onClick={onClose}
                className={cn(
                  'rounded-lg p-2 transition-colors',
                  'hover:bg-background-alt',
                  'text-text-secondary hover:text-text-primary'
                )}
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {isLoading && (
                <div className="flex items-center justify-center h-48">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
              )}

              {error && (
                <div className="rounded-lg bg-error-bg text-error-text p-4">
                  <p className="text-sm font-medium">Error loading skill</p>
                  <p className="text-sm mt-1">{error}</p>
                </div>
              )}

              {!isLoading && !error && skill && (
                <div className="space-y-6">
                  {/* Metadata */}
                  <div className="space-y-4">
                    {/* Description */}
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary mb-2">
                        Description
                      </h3>
                      <p className="text-sm text-text-secondary leading-relaxed">
                        {skill.description}
                      </p>
                    </div>

                    {/* File Path */}
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
                        <BookOpen className="w-4 h-4" />
                        File Path
                      </h3>
                      <code className="block rounded-lg bg-background px-3 py-2 text-sm font-mono text-text-secondary">
                        {skill.file_path}
                      </code>
                    </div>

                    {/* Tools */}
                    {skill.tools && skill.tools.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
                          <Wrench className="w-4 h-4" />
                          Required Tools ({skill.tools.length})
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {skill.tools.map((tool) => (
                            <span
                              key={tool}
                              className="rounded-lg bg-background-alt px-3 py-1.5 text-sm font-mono text-text-secondary border border-border"
                            >
                              {tool}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Full Content */}
                  {content && (
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary mb-2">
                        Full Content
                      </h3>
                      <div className="rounded-lg bg-background p-4 border border-border">
                        <pre className="text-sm text-text-secondary whitespace-pre-wrap font-mono">
                          {content}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-border p-4 bg-background-alt">
              <button
                onClick={onClose}
                className={cn(
                  'w-full rounded-lg px-4 py-2.5',
                  'bg-primary text-white font-medium text-sm',
                  'hover:bg-primary-hover',
                  'transition-colors'
                )}
              >
                Close
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
