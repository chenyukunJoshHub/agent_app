'use client';

import type { ContextWindowData, SlotDetail, StateMessage, SessionMeta } from '@/types/context-window';
import { SessionMetadataSection } from './context/SessionMetadataSection';
import { TokenMapSection } from './context/TokenMapSection';
import { SlotCardsSection } from './context/SlotCardsSection';
import { CompressionLog } from './CompressionLog';

interface ContextPanelProps {
  sessionMeta: SessionMeta | null;
  contextWindowData: ContextWindowData;
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
  /** Unix timestamp（ms）—由 page.tsx 在 done 事件时更新 */
  lastActivityTime: number | null;
}

export function ContextPanel({
  sessionMeta,
  contextWindowData,
  slotDetails,
  stateMessages,
  lastActivityTime,
}: ContextPanelProps) {
  const hasCompressionEvents = contextWindowData.compressionEvents.length > 0;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Module 1: 会话元数据与 Token 统计 */}
      <SessionMetadataSection
        sessionMeta={sessionMeta}
        budget={contextWindowData.budget}
        stateMessages={stateMessages}
        lastActivityTime={lastActivityTime}
      />

      {/* Module 2: 上下文窗口 · Token 地图 */}
      <TokenMapSection
        budget={contextWindowData.budget}
        slotUsage={contextWindowData.slotUsage}
      />

      {/* Module 3: 各 Slot 原文与 Prompt */}
      <SlotCardsSection
        slotDetails={slotDetails}
        stateMessages={stateMessages}
      />

      {/* Module 4: 压缩日志（仅有事件时显示） */}
      {hasCompressionEvents && (
        <div>
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <div style={{ width: 4, height: 20, background: '#6B7280', borderRadius: 2, flexShrink: 0 }} />
            <span className="text-sm font-bold text-text-primary">④ 压缩日志</span>
          </div>
          <CompressionLog
            events={contextWindowData.compressionEvents}
            hideInternalHeader={true}
          />
        </div>
      )}
    </div>
  );
}
