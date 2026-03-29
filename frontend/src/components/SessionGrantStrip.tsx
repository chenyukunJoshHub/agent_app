'use client';

import { cn } from '@/lib/utils';

interface SessionGrantStripProps {
  grants: string[];
  onRevoke: (toolName: string) => void;
  className?: string;
}

export function SessionGrantStrip({ grants, onRevoke, className }: SessionGrantStripProps) {
  if (grants.length === 0) {
    return null;
  }

  return (
    <div className={cn('border-b border-border/60 bg-bg-alt/60 px-4 py-3', className)}>
      <div className="text-xs text-text-muted">本会话已放行</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {grants.map((toolName) => (
          <div
            key={toolName}
            className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-800"
          >
            <span className="font-mono">{toolName}</span>
            <button
              type="button"
              className="rounded-full px-1.5 py-0.5 text-[11px] font-medium text-emerald-900 transition hover:bg-emerald-100"
              onClick={() => onRevoke(toolName)}
              aria-label={`撤销 ${toolName} 会话放行`}
            >
              撤销
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
