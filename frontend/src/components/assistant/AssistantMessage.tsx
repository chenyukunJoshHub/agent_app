/**
 * AssistantMessage — message wrapper using assistant-ui primitives.
 *
 * Currently NOT used directly (MessageList renders messages).
 * Provided for future migration to full primitive-based rendering.
 */
'use client';

import { MessagePrimitive } from '@assistant-ui/react';
import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AssistantMessageProps {
  className?: string;
  children?: React.ReactNode;
}

export function AssistantMessage({ className, children }: AssistantMessageProps) {
  return (
    <MessagePrimitive.Root
      className={cn(
        'group/message relative flex gap-3 px-6 py-4',
        'hover:bg-bg-alt/50',
        'transition-colors duration-200',
        className,
      )}
    >
      <MessagePrimitive.If role="assistant">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-lg shadow-md bg-gradient-to-br from-primary to-secondary"
        >
          <Bot className="h-4 w-4 text-white" />
        </motion.div>
      </MessagePrimitive.If>
      <MessagePrimitive.If role="user">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-lg shadow-md bg-gradient-to-br from-blue-500 to-blue-600"
        >
          <User className="h-4 w-4 text-white" />
        </motion.div>
      </MessagePrimitive.If>
      {children ?? <MessagePrimitive.Content />}
    </MessagePrimitive.Root>
  );
}
