/**
 * AssistantRoot - assistant-ui 根容器自定义
 * 匹配设计系统的主题和样式
 */

'use client';

import { Root as AssistantUIRoot } from '@assistant-ui/react';
import { cn } from '@/lib/utils';

interface AssistantRootProps extends React.ComponentProps<typeof AssistantUIRoot> {}

export function AssistantRoot({ className, ...props }: AssistantRootProps) {
  return (
    <AssistantUIRoot
      className={cn(
        // 基础布局
        'flex h-screen flex-col bg-bg-base text-text-primary',

        // Focus 状态
        'focus-within:ring-2 focus-within:ring-primary/20 focus-within:ring-inset',

        // 平滑过渡
        'transition-all duration-200',

        className
      )}
      {...props}
    />
  );
}
