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
      {/* <div className="flex items-center gap-2 px-4 py-3">
        <div
          data-testid="module2-accent"
          style={{ width: 4, height: 20, background: '#6366F1', borderRadius: 2, flexShrink: 0 }}
        />
        <span className="text-sm font-bold text-text-primary">② 上下文窗口 · Token 地图</span>
      </div> */}

      <div className="mx-4 mb-4 rounded-lg  bg-bg-card p-3 mt-4">
        {/* Subtitle */}
        <div className="mb-2 text-[10px] font-semibold text-text-muted">
          context window Token 占比（{wbLabel} ）
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

        {/* Detail table with color dots */}
        <div className="font-mono text-[12px] leading-relaxed text-text-secondary space-y-[2px]">
          {tableRows.map((s) => {
            const label = SLOT_DISPLAY_NAMES[s.key as keyof typeof SLOT_DISPLAY_NAMES] ?? s.key;
            const tokStr = s.tokens > 0 ? formatTokens(s.tokens) : '—';
            const pctStr = s.tokens > 0 ? formatPct(s.tokens, wb) : '—';
            const allocated = budget.slots[s.key as keyof typeof budget.slots] ?? 0;
            // system slot 预算是多个子项组合，不准确，不显示；history 是弹性 slot，显示"弹性"
            let budgetStr: string;
            if (s.key === 'history') {
              budgetStr = '弹性';
            } else if (s.key === 'system') {
              budgetStr = '';
            } else {
              budgetStr = allocated > 0 ? formatTokens(allocated) : '∞';
            }
            return (
              <div key={s.key} className="flex items-center gap-1.5 whitespace-pre">
                <span
                  className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                  style={{ background: s.color }}
                />
                <span>{label.padEnd(8)}</span>
                <span className="tabular-nums">{tokStr.padStart(6)}</span>
                <span className="tabular-nums">{pctStr.padStart(6)}</span>
                {budgetStr && (
                  <span className="tabular-nums text-text-muted">{budgetStr.padStart(6)}</span>
                )}
              </div>
            );
          })}
          <div className="flex items-center gap-1.5 whitespace-pre">
            <span
              className="inline-block h-2 w-2 rounded-full flex-shrink-0"
              style={{ background: CONTEXT_REMAINING_FREE_COLOR }}
            />
            <span>{'剩余可用'.padEnd(8)}</span>
            <span className="tabular-nums">{formatTokens(remaining).padStart(6)}</span>
            <span className="tabular-nums">{formatPct(remaining, wb).padStart(6)}</span>
            <span className="tabular-nums text-text-muted">{''.padStart(6)}</span>
          </div>
          <div className="flex items-center gap-1.5 whitespace-pre">
            <span
              className="inline-block h-2 w-2 rounded-full flex-shrink-0"
              style={{ background: CONTEXT_AUTOCOMPACT_BUFFER_COLOR }}
            />
            <span>{'安全余量'.padEnd(8)}</span>
            <span className="tabular-nums">{formatTokens(autocompact).padStart(6)}</span>
            <span className="tabular-nums">{formatPct(autocompact, wb).padStart(6)}</span>
            <span className="tabular-nums text-text-muted">{''.padStart(6)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
