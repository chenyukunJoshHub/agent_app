'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Wrench,
  CheckCircle,
  Flag,
  XCircle,
  Hand,
  Sparkles,
  ChevronDown,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export interface TimelineEvent {
  id: string;
  type: 'thought' | 'tool_start' | 'tool_result' | 'done' | 'error' | 'hil_interrupt';
  content: string;
  toolName?: string;
  timestamp: number;
}

interface TimelineProps {
  events: TimelineEvent[];
}

export function Timeline({ events }: TimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const getEventIcon = (type: TimelineEvent['type']) => {
    const iconClassName = "w-4 h-4";

    switch (type) {
      case 'thought':
        return <Brain className={iconClassName} />;
      case 'tool_start':
        return <Wrench className={iconClassName} />;
      case 'tool_result':
        return <CheckCircle className={iconClassName} />;
      case 'done':
        return <Flag className={iconClassName} />;
      case 'error':
        return <XCircle className={iconClassName} />;
      case 'hil_interrupt':
        return <Hand className={iconClassName} />;
      default:
        return <Sparkles className={iconClassName} />;
    }
  };

  const getEventColor = (type: TimelineEvent['type']) => {
    switch (type) {
      case 'thought':
        return 'border-react-thought bg-blue-50 dark:bg-blue-900/20';
      case 'tool_start':
        return 'border-react-tool-call bg-yellow-50 dark:bg-yellow-900/20';
      case 'tool_result':
        return 'border-react-tool-result bg-green-50 dark:bg-green-900/20';
      case 'done':
        return 'border-react-final bg-purple-50 dark:bg-purple-900/20';
      case 'error':
        return 'border-danger bg-red-50 dark:bg-red-900/20';
      case 'hil_interrupt':
        return 'border-react-interrupt bg-orange-50 dark:bg-orange-900/20';
      default:
        return 'border-border bg-background-muted dark:bg-background-muted';
    }
  };

  const getEventIconColor = (type: TimelineEvent['type']) => {
    switch (type) {
      case 'thought':
        return 'text-react-thought';
      case 'tool_start':
        return 'text-react-tool-call';
      case 'tool_result':
        return 'text-react-tool-result';
      case 'done':
        return 'text-react-final';
      case 'error':
        return 'text-danger';
      case 'hil_interrupt':
        return 'text-react-interrupt';
      default:
        return 'text-muted-foreground';
    }
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4 bg-background-alt">
        <h2 className="font-semibold text-text-primary">时间轴</h2>
        <p className="mt-1 text-xs text-muted-foreground">{events.length} 个事件</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {events.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">暂无事件</p>
          </div>
        ) : (
          <div className="relative space-y-4">
            {/* Vertical line */}
            <div className="absolute left-4 top-0 h-full w-0.5 bg-border" />

            {events.map((event, index) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.1 }}
                className="relative pl-10"
              >
                {/* Event node */}
                <div
                  className={cn(
                    "absolute left-2 top-1 flex h-6 w-6 items-center justify-center rounded-full border-2 bg-background text-sm",
                    getEventColor(event.type)
                  )}
                >
                  {getEventIcon(event.type)}
                </div>

                {/* Event content */}
                <div
                  className={cn(
                    "rounded-lg border p-3 shadow-sm",
                    getEventColor(event.type)
                  )}
                >
                  {/* Event header */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase text-text-secondary">
                        {event.type}
                      </span>
                      {event.toolName && (
                        <span className="font-mono text-xs font-medium text-text-primary bg-background px-2 py-0.5 rounded">
                          {event.toolName}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimestamp(event.timestamp)}
                    </span>
                  </div>

                  {/* Event content */}
                  <p className="mt-2 text-sm text-text-primary">{event.content}</p>
                </div>
              </motion.div>
            ))}
          </div>
        )}
        <div ref={scrollRef} />
      </div>
    </div>
  );
}
