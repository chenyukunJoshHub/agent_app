'use client';

import type { TokenBudgetState, SlotUsage } from '@/types/context-window';
import {
  SLOT_VISUAL_ORDER,
  SLOT_COLORS,
  SLOT_DISPLAY_NAMES,
  CONTEXT_REMAINING_FREE_COLOR,
  CONTEXT_AUTOCOMPACT_BUFFER_COLOR,
} from '@/types/context-window';

interface TokenMapSectionProps {
  budget: TokenBudgetState;
  slotUsage: SlotUsage[];
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatPct(part: number, total: number) {
  if (total === 0) return '0.0%';
  return `${((part / total) * 100).toFixed(1)}%`;
}

export function TokenMapSection({ budget, slotUsage }: TokenMapSectionProps) {
  const wb = budget.working_budget;
  const autocompact = budget.usage.autocompact_buffer ?? 0;

  // Build slot token map from slotUsage (used), falling back to budget.slots (allocated)
  const slotUsageMap = Object.fromEntries(slotUsage.map((s) => [s.name, s.used]));
  const segments = SLOT_VISUAL_ORDER.map((key) => ({
    key,
    tokens: slotUsageMap[key] ?? budget.slots[key] ?? 0,
    color: SLOT_COLORS[key],
  }));

  const totalSlotTokens = segments.reduce((sum, s) => sum + s.tokens, 0);
  const remaining = Math.max(0, wb - totalSlotTokens - autocompact);

  const barSegments = [
    ...segments,
    { key: 'remaining', tokens: remaining, color: CONTEXT_REMAINING_FREE_COLOR },
    { key: 'autocompact', tokens: autocompact, color: CONTEXT_AUTOCOMPACT_BUFFER_COLOR },
  ];

  // Table rows: all slots (show — for zero-token slots)
  const tableRows = segments;

  const wbLabel = wb >= 1000 ? `${Math.round(wb / 1024)}k` : String(wb);

  return (
    <div className="border-b border-border">
      {/* Section header */}
      <div className="flex items-center gap-2 px-4 py-3">
        <div
          data-testid="module2-accent"
          style={{ width: 4, height: 20, background: '#6366F1', borderRadius: 2, flexShrink: 0 }}
        />
        <span className="text-sm font-bold text-text-primary">② 上下文窗口 · Token 地图</span>
      </div>

      <div className="mx-4 mb-4 rounded-lg border border-border bg-bg-card p-3">
        {/* Subtitle */}
        <div className="mb-2 text-[10px] font-semibold text-text-muted">
          10 档 Token 占比（{wbLabel} 工作窗口）
        </div>

        {/* 12-segment proportional bar — flex sizing avoids division-by-zero */}
        <div data-testid="token-bar" className="mb-3 flex h-2 overflow-hidden rounded">
          {barSegments.map((seg) => (
            <div
              key={seg.key}
              style={{
                flex: Math.max(seg.tokens, 0),
                background: seg.color,
                minWidth: seg.tokens > 0 ? 2 : 0,
              }}
            />
          ))}
        </div>

        {/* Monospace detail table */}
        <pre className="font-mono text-[9px] leading-relaxed text-text-secondary">
          {tableRows
            .map((s) => {
              const label = SLOT_DISPLAY_NAMES[s.key as keyof typeof SLOT_DISPLAY_NAMES] ?? s.key;
              const tokStr = s.tokens > 0 ? formatTokens(s.tokens) : '—';
              const pctStr = s.tokens > 0 ? formatPct(s.tokens, wb) : '—';
              return `${label.padEnd(8)}  ${tokStr.padStart(6)}  ${pctStr.padStart(6)}\n`;
            })
            .join('')}
          {`剩余可用  ${formatTokens(remaining).padStart(6)}  ${formatPct(remaining, wb).padStart(6)}\n`}
          {`压缩预留  ${formatTokens(autocompact).padStart(6)}  ${formatPct(autocompact, wb).padStart(6)}`}
        </pre>
      </div>
    </div>
  );
}
