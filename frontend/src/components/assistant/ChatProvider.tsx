/**
 * ChatProvider — wraps children with assistant-ui's AssistantRuntimeProvider.
 *
 * Accepts an onSendMessage callback (from useSSEHandlers in page.tsx)
 * so the runtime can bridge assistant-ui's composer → SSE stream.
 */
'use client';

import { AssistantRuntimeProvider } from '@assistant-ui/react';
import { useChatRuntime } from '@/lib/chat-runtime';
import type { SendMessageFn } from '@/lib/chat-runtime';

export function ChatProvider({
  children,
  onSendMessage,
}: {
  children: React.ReactNode;
  onSendMessage: SendMessageFn;
}) {
  const runtime = useChatRuntime(onSendMessage);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
