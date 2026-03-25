/**
 * AssistantThreadWelcome - 欢迎界面组件
 * 可选的替代空状态界面
 */

'use client';

import { motion } from 'framer-motion';
import { Bot, Sparkles, Zap, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AssistantThreadWelcomeProps {
  className?: string;
  title?: string;
  description?: string;
  examples?: string[];
}

export function AssistantThreadWelcome({
  className,
  title = 'Multi-Tool AI Agent',
  description = '企业级 AI Agent • 全链路可视化',
  examples = [
    '帮我查一下茅台今天的股价',
    '分析最近一周的科技新闻趋势',
    '生成一份 React 项目架构图',
  ],
}: AssistantThreadWelcomeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn('flex h-full items-center justify-center min-h-[400px]', className)}
    >
      <div className="text-center px-6">
        {/* Logo with glow */}
        <motion.div
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="relative inline-block mb-8"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-primary to-secondary blur-3xl opacity-20" />
          <div className="relative w-24 h-24 mx-auto rounded-3xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-glow-primary">
            <Bot className="w-12 h-12 text-white" />
          </div>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="text-4xl font-bold text-text-primary mb-3"
        >
          {title}
        </motion.h1>

        {/* Description */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-lg text-text-muted mb-12"
        >
          {description}
        </motion.p>

        {/* Features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="flex justify-center gap-8 mb-12"
        >
          {[
            { icon: Sparkles, label: '智能编排' },
            { icon: Zap, label: '实时响应' },
            { icon: Shield, label: '安全可控' },
          ].map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 + i * 0.1 }}
              className="flex flex-col items-center gap-2"
            >
              <div className="w-12 h-12 rounded-xl bg-bg-card border border-border flex items-center justify-center text-primary">
                <feature.icon className="w-5 h-5" />
              </div>
              <span className="text-sm text-text-secondary">{feature.label}</span>
        </motion.div>
          ))}
        </motion.div>

        {/* Example Prompts */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="space-y-3 max-w-lg mx-auto"
        >
          <p className="text-xs text-text-muted uppercase tracking-wider mb-4">
            试试这些
          </p>
          {examples.map((example, i) => (
            <motion.button
              key={i}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.9 + i * 0.1 }}
              whileHover={{ scale: 1.02, x: 4 }}
              className={cn(
                'w-full block px-5 py-4 rounded-xl text-left',
                'border border-border bg-bg-card text-text-secondary',
                'hover:border-primary hover:text-primary hover:bg-bg-alt hover:shadow-glow-primary',
                'transition-all duration-200'
              )}
            >
              {example}
            </motion.button>
          ))}
        </motion.div>
      </div>
    </motion.div>
  );
}
