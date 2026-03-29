'use client';

import type { SessionMeta, TokenBudgetState, StateMessage } from '@/types/context-window';

interface SessionMetadataSectionProps {
  sessionMeta: SessionMeta | null;
  budget: TokenBudgetState;
  stateMessages: StateMessage[];
  /** Unix timestamp（ms）—由父组件在 done 事件时更新 */
  lastActivityTime: number | null;
  sessionGrants?: string[];
  onRevokeTool?: (toolName: string) => void;
}

function formatNumber(n: number) {
  return n.toLocaleString('zh-CN');
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

function formatLastActivity(ts: number | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getUsageColorClass(pct: number): string {
  if (pct >= 90) return 'text-error-text';
  if (pct >= 70) return 'text-warning-text';
  return 'text-success-text';
}

export function SessionMetadataSection({
  sessionMeta,
  budget,
  stateMessages,
  lastActivityTime,
  sessionGrants = [],
  onRevokeTool,
}: SessionMetadataSectionProps) {
  const usagePct =
    budget.working_budget > 0 ? (budget.usage.total_used / budget.working_budget) * 100 : 0;
  const usageStr = `${usagePct.toFixed(1)}%`;

  const userCount = stateMessages.filter((m) => m.role === 'user').length;
  const assistantCount = stateMessages.filter((m) => m.role === 'assistant').length;
  const totalMessages = stateMessages.length;

  return (
    <div className="border-b border-border">
      {/* Section header */}
      <div className="flex items-center gap-2 px-4 py-3">
        {/* <div
          data-testid="module1-accent"
          style={{ width: 4, height: 20, background: '#2563EB', borderRadius: 2, flexShrink: 0 }}
        /> */}
        {/* <span className="text-sm font-bold text-text-primary">① 会话元数据与 Token 统计</span> */}
      </div>

      {/* 2-col metadata grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-4 pb-4 text-xs">
        {/* Row 1 */}
        <div>
          <div className="text-text-muted">会话名称</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {sessionMeta?.session_name ?? '—'}
          </div>
        </div>
           {/* Row 2 */}
        <div>
          <div className="text-text-muted">上下文限制</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {formatNumber(budget.model_context_window)} tokens
          </div>
        </div>

         <div>
          <div className="text-text-muted">激活模型</div>
          <div className="mt-0.5 truncate font-semibold text-text-primary">
            {sessionMeta?.model ?? '—'}
          </div>
        </div>
         <div>
          <div className="text-text-muted">工作窗口</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {formatTokens(budget.working_budget)}
          </div>
        </div>

       
       
        {/* Row 3 */}
        <div>
          <div className="text-text-muted">已用 token</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {formatTokens(budget.usage.total_used)}
          </div>
        </div>


        {/* Row 4 */}
        <div>
          <div className="text-text-muted">可用 token</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {formatTokens(budget.usage.total_remaining)}
          </div>
        </div>
        <div>
          <div className="text-text-muted">使用率</div>
          <div
            data-testid="usage-rate"
            className={`mt-0.5 font-semibold ${getUsageColorClass(usagePct)}`}
          >
            {usageStr}
          </div>
        </div>

      <div>
          <div className="text-text-muted">消息数量</div>
          <div className="mt-0.5 font-semibold text-text-primary">{totalMessages}</div>
        </div>
     

        {/* Row 5 */}
        <div>
          <div className="text-text-muted">用户消息</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            <span data-testid="user-messages-count">{userCount}</span>
          </div>
        </div>
        <div>
          <div className="text-text-muted">助手消息</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            <span data-testid="assistant-messages-count">{assistantCount}</span>
          </div>
        </div>

        {/* Row 6 */}

      </div>

      {sessionGrants.length > 0 && (
        <div className="border-t border-border/80 px-4 pb-4 pt-3">
          <div className="text-xs text-text-muted">本会话已放行</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {sessionGrants.map((toolName) => (
              <div
                key={toolName}
                className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-800"
              >
                <span className="font-mono">{toolName}</span>
                {onRevokeTool && (
                  <button
                    type="button"
                    className="rounded-full px-1.5 py-0.5 text-[11px] font-medium text-emerald-900 transition hover:bg-emerald-100"
                    onClick={() => onRevokeTool(toolName)}
                    aria-label={`撤销 ${toolName} 会话放行`}
                  >
                    撤销
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
