'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SlotDetail, StateMessage } from '@/types/context-window';

interface SlotCardsSectionProps {
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function SlotCardsSection({ slotDetails, stateMessages }: SlotCardsSectionProps) {
  const [expandedSlots, setExpandedSlots] = useState<Set<string>>(new Set());

  const sorted = [...slotDetails].sort((a, b) => b.tokens - a.tokens);

  const toggle = (name: string, enabled: boolean) => {
    if (!enabled) return;
    setExpandedSlots(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div className="border-b border-border">
      {/* Section header */}
      {/* <div className="flex items-center gap-2 px-4 py-3">
        <div
          data-testid="module3-accent"
          style={{ width: 4, height: 20, background: '#0D9488', borderRadius: 2, flexShrink: 0 }}
        />
        <span className="text-sm font-bold text-text-primary">③ 各 Slot 原文与 Prompt</span>
      </div> */}

      <div className="flex flex-col gap-1 px-4 pb-4 mt-4">
        {sorted.length === 0 && (
          <p className="py-2 text-xs text-text-muted">暂无 Slot 数据</p>
        )}
        {sorted.map(slot => {
          const isHistory = slot.name === 'history';
          const isExpanded = expandedSlots.has(slot.name);

          return (
            <div
              key={slot.name}
              data-testid={`slot-card-${slot.name}`}
              className={cn(
                'rounded-lg border border-border bg-bg-card',
                !slot.enabled && 'pointer-events-none opacity-40',
                slot.enabled && 'cursor-pointer hover:border-border-strong',
              )}
              onClick={() => toggle(slot.name, slot.enabled)}
            >
              {/* Card header row */}
              <div className="flex items-center justify-between px-3 py-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-xs font-semibold text-text-primary">
                    {slot.display_name}
                  </span>
                  <span className="shrink-0 font-mono text-[10px] text-text-muted">
                    {formatTokens(slot.tokens)}
                  </span>
                </div>
                <div className="shrink-0 text-text-muted">
                  {isHistory
                    ? <ChevronsUpDown className="h-3.5 w-3.5" />
                    : isExpanded
                    ? <ChevronUp className="h-3.5 w-3.5" />
                    : <ChevronDown className="h-3.5 w-3.5" />
                  }
                </div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className="border-t border-border px-3 pb-3 pt-2">
                  {isHistory ? (
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[9px] leading-relaxed text-text-secondary">
                      {stateMessages.map(m => JSON.stringify(m, null, 2)).join('\n')}
                    </pre>
                  ) : (
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[9px] leading-relaxed text-text-secondary">
                      {slot.content}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
