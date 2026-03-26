/**
 * AssistantMessage - 消息组件自定义
 * 优化视觉层次和交互反馈
 */

'use client';

import { Message as AssistantUIMessage } from '@assistant-ui/react';
import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AssistantMessageProps extends React.ComponentProps<typeof AssistantUIMessage> {}

export function AssistantMessage({ className, ...props }: AssistantMessageProps) {
  return (
    <AssistantUIMessage
      className={cn(
        // 基础布局
        'group/message relative flex gap-3 px-6 py-4',

        // 悬停效果
        'hover:bg-bg-alt/50',

        // 平滑过渡
        'transition-colors duration-200',

        className
      )}
      components={{
        Avatar: ({ role }) => (
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.2 }}
            className={cn(
              'flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-lg shadow-md',
              role === 'assistant'
                ? 'bg-gradient-to-br from-primary to-secondary'
                : 'bg-gradient-to-br from-blue-500 to-blue-600'
            )}
          >
            {role === 'assistant' ? (
              <Bot className="h-4 w-4 text-white" />
            ) : (
              <User className="h-4 w-4 text-white" />
            )}
          </motion.div>
        ),
      }}
      {...props}
    />
  );
}
