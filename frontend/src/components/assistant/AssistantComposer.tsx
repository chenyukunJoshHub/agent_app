/**
 * AssistantComposer - 输入框组件自定义
 * 增强输入体验和视觉反馈
 */

'use client';

import { Composer as AssistantUIComposer } from '@assistant-ui/react';
import { motion } from 'framer-motion';
import { Send, Loader2, Paperclip } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface AssistantComposerProps extends React.ComponentProps<typeof AssistantUIComposer> {}

export function AssistantComposer({ className, ...props }: AssistantComposerProps) {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <AssistantUIComposer
      className={cn(
        // 容器样式
        'border-t border-border bg-bg-alt p-4',
        'transition-colors duration-300',

        className
      )}
      components={{
        Root: ({ children }) => (
          <div className="mx-auto max-w-4xl">{children}</div>
        ),

        Input: ({ value, onChange, onSend, disabled }) => (
          <div
            className={cn(
              'flex items-end gap-3 transition-all duration-200',
              isFocused && 'scale-[1.01]'
            )}
          >
            {/* 附件按钮 */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={cn(
                'flex h-12 w-12 items-center justify-center rounded-xl',
                'border border-border bg-bg-card text-text-muted',
                'hover:border-primary hover:text-primary',
                'transition-all duration-200',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
              disabled={disabled}
            >
              <Paperclip className="h-5 w-5" />
            </motion.button>

            {/* 输入框 */}
            <div className="flex-1 relative">
              <textarea
                value={value}
                onChange={(e) => onChange?.(e.target.value)}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                placeholder="描述任务，例如：帮我查一下茅台今天的股价..."
                className={cn(
                  'w-full resize-none rounded-xl border border-border',
                  'bg-bg-card px-4 py-3 text-sm text-text-primary',
                  'placeholder:text-text-muted',
                  'focus:border-primary focus:ring-2 focus:ring-primary/10',
                  'focus:outline-none transition-all duration-200',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'min-h-[48px] max-h-[200px]'
                )}
                rows={1}
                disabled={disabled}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    onSend?.();
                  }
                }}
              />

              {/* 字符计数 */}
              {value && value.length > 0 && (
                <div className="absolute bottom-3 right-3 text-xs text-text-muted">
                  {value.length} 字符
                </div>
              )}
            </div>

            {/* 发送按钮 */}
            <motion.button
              onClick={onSend}
              whileHover={{ scale: disabled ? 1 : 1.02 }}
              whileTap={{ scale: disabled ? 1 : 0.98 }}
              className={cn(
                'flex h-12 min-w-[100px] items-center justify-center gap-2 rounded-xl',
                'bg-primary px-5 py-3 text-sm font-semibold text-white',
                'hover:bg-primary-hover',
                'disabled:bg-muted disabled:cursor-not-allowed',
                'transition-all duration-200',
                'shadow-glow-primary'
              )}
              disabled={disabled || !value?.trim()}
            >
              {disabled ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  发送中...
                </>
              ) : (
                <>
                  发送
                  <Send className="h-4 w-4" />
                </>
              )}
            </motion.button>
          </div>
        ),
      }}
      {...props}
    />
  );
}
