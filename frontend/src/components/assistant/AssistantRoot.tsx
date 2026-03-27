/**
 * AssistantRoot — structural wrapper for the thread.
 *
 * Uses ThreadPrimitive.Root for assistant-ui runtime context.
 */
'use client';

import { ThreadPrimitive } from '@assistant-ui/react';
import { cn } from '@/lib/utils';

interface AssistantRootProps {
  className?: string;
  children?: React.ReactNode;
}

export function AssistantRoot({ className, children }: AssistantRootProps) {
  return (
    <ThreadPrimitive.Root
      className={cn(
        'flex h-full flex-col bg-bg-base text-text-primary',
        'focus-within:ring-2 focus-within:ring-primary/20 focus-within:ring-inset',
        'transition-all duration-200',
        className,
      )}
    >
      {children}
    </ThreadPrimitive.Root>
  );
}
