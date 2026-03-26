/**
 * AssistantThread - 会话线程组件自定义
 * 集成现有 SSE 流式响应
 */

'use client';

import { ThreadMessages as AssistantUIThreadMessages } from '@assistant-ui/react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AssistantThreadProps extends React.ComponentProps<typeof AssistantUIThreadMessages> {}

export function AssistantThread({ className, ...props }: AssistantThreadProps) {
  return (
    <AssistantUIThreadMessages
      className={cn(
        'flex-1 overflow-y-auto',
        className
      )}
      components={{
        Empty: () => (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex h-full items-center justify-center min-h-[400px]"
          >
            <div className="text-center">
              {/* Logo */}
              <motion.div
                initial={{ y: -20 }}
                animate={{ y: 0 }}
                transition={{ delay: 0.1 }}
                className="relative inline-block mb-6"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-primary to-secondary blur-2xl opacity-30" />
                <div className="relative w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-glow-primary">
                  <Bot className="w-10 h-10 text-white" />
                </div>
              </motion.div>

              {/* 欢迎标题 */}
              <motion.h2
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="text-3xl font-semibold text-text-primary mb-3"
              >
                Multi-Tool AI Agent
              </motion.h2>

              {/* 副标题 */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="text-text-muted mb-8"
              >
                企业级 AI Agent • 全链路可视化
              </motion.p>

              {/* 示例提示 */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="space-y-3"
              >
                {[
                  '帮我查一下茅台今天的股价',
                  '分析最近一周的科技新闻趋势',
                  '生成一份 React 项目架构图',
                ].map((example, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + i * 0.1 }}
                    whileHover={{ scale: 1.02, x: 4 }}
                    className={cn(
                      'w-full max-w-md mx-auto block px-4 py-3 rounded-xl',
                      'border border-border bg-bg-card text-text-secondary text-sm',
                      'hover:border-primary hover:text-primary hover:bg-bg-alt',
                      'transition-all duration-200'
                    )}
                  >
                    {example}
                  </motion.button>
                ))}
              </motion.div>
            </div>
          </motion.div>
        ),

        Loading: () => (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 px-6 py-4"
          >
            {/* Avatar */}
            <div className="flex-shrink-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-md">
                <Bot className="w-4 h-4 text-white" />
              </div>
            </div>

            {/* Loading Indicator */}
            <div className="bg-bg-card border border-border rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{
                        duration: 0.6,
                        repeat: Infinity,
                        delay: i * 0.1,
                      }}
                      className="w-2 h-2 rounded-full bg-primary"
                    />
                  ))}
                </div>
                <span className="text-sm text-text-muted">思考中...</span>
              </div>
            </div>
          </motion.div>
        ),
      }}
      {...props}
    />
  );
}
