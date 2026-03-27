/**
 * AssistantThread — message viewport wrapper.
 *
 * Uses ThreadPrimitive.Viewport for scroll management, but renders
 * our custom MessageList inside it (preserves markdown + tool call rendering).
 */
'use client';

import { ThreadPrimitive } from '@assistant-ui/react';
import type { Message } from '@/store/use-session';
import type { StateMessage } from '@/types/context-window';
import { MessageList } from '@/components/MessageList';
import { cn } from '@/lib/utils';

interface AssistantThreadProps {
  messages: Message[];
  isLoading: boolean;
  stateMessages: StateMessage[];
  compressionEvents: unknown[];
  className?: string;
}

export function AssistantThread({
  messages,
  isLoading,
  stateMessages,
  compressionEvents,
  className,
}: AssistantThreadProps) {
  return (
    <ThreadPrimitive.Viewport className={cn('flex-1 overflow-y-auto', className)}>
      <MessageList
        messages={messages}
        isLoading={isLoading}
        stateMessages={stateMessages}
        compressionEvents={compressionEvents}
      />
    </ThreadPrimitive.Viewport>
  );
}
