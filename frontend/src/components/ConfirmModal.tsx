'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  X,
  ChevronDown,
  ChevronRight,
  Check,
  X as XIcon,
  Wrench,
} from 'lucide-react';
import type { InterruptData } from '@/hooks/useSSEHandlers';
import { cn } from '@/lib/utils';

interface ConfirmModalProps {
  isOpen: boolean;
  interrupt: InterruptData | null;
  onConfirm: (interruptId: string, grantSession: boolean) => void;
  onCancel: (interruptId: string) => void;
}

export function ConfirmModal({ isOpen, interrupt, onConfirm, onCancel }: ConfirmModalProps) {
  const [showParams, setShowParams] = useState(false);
  const [grantSession, setGrantSession] = useState(false);

  if (!isOpen || !interrupt) {
    return null;
  }

  const { interrupt_id, tool_name, tool_args, risk_level, message } = interrupt;
  const actionRequests =
    interrupt.action_requests && interrupt.action_requests.length > 0
      ? interrupt.action_requests
      : [{ name: tool_name, args: tool_args }];
  const uniqueToolNames = new Set(actionRequests.map((action) => action.name));
  const canGrantSession =
    interrupt.grant_session_supported ?? uniqueToolNames.size === 1;
  const grantTargetTool = canGrantSession ? actionRequests[0]?.name ?? tool_name : null;

  const riskConfig = {
    high: {
      color:
        'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-200 dark:border-red-700',
      iconColor: 'text-red-600 dark:text-red-400',
      label: '高风险',
      icon: AlertTriangle,
    },
    medium: {
      color:
        'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-200 dark:border-yellow-700',
      iconColor: 'text-yellow-600 dark:text-yellow-400',
      label: '中风险',
      icon: AlertTriangle,
    },
    low: {
      color:
        'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/20 dark:text-green-200 dark:border-green-700',
      iconColor: 'text-green-600 dark:text-green-400',
      label: '低风险',
      icon: Check,
    },
  };

  const config = riskConfig[risk_level];
  const RiskIcon = config.icon;

  const handleConfirm = () => {
    onConfirm(interrupt_id, grantSession);
    setGrantSession(false);
  };

  const handleCancel = () => {
    onCancel(interrupt_id);
    setShowParams(false);
    setGrantSession(false);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 200 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
            onClick={handleCancel}
          >
            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 200, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-lg rounded-2xl bg-background shadow-xl border border-border"
              onClick={(e) => e.stopPropagation()}
              data-testid="confirm-modal"
            >
              {/* Header */}
              <div className="border-b border-border p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h2 className="text-xl font-semibold text-text-primary">确认操作</h2>
                    <p className="mt-1 text-sm text-text-secondary">{message}</p>
                  </div>
                  <button
                    onClick={handleCancel}
                    className="flex-shrink-0 rounded-lg p-2 text-muted-foreground hover:text-text-secondary
                                   hover:bg-background transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                {/* Risk Badge */}
                <div
                  className={cn(
                    'mt-4 inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium',
                    config.color
                  )}
                >
                  <RiskIcon className={cn('w-4 h-4', config.iconColor)} />
                  {config.label}
                </div>
              </div>

              {/* Content */}
              <div className="p-6 space-y-4">
                {actionRequests.length === 1 ? (
                  <>
                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        操作工具
                      </label>
                      <div className="rounded-lg bg-background-muted px-4 py-3 text-sm font-mono text-text-primary border border-border">
                        <Wrench className="w-4 h-4 inline mr-2 text-primary" />
                        {tool_name}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium text-text-primary">操作参数</label>
                        <button
                          onClick={() => setShowParams(!showParams)}
                          className="text-xs text-primary hover:text-primary-hover transition-colors flex items-center gap-1"
                        >
                          {showParams ? (
                            <>
                              <ChevronDown className="w-3 h-3" />
                              收起
                            </>
                          ) : (
                            <>
                              <ChevronRight className="w-3 h-3" />
                              展开
                            </>
                          )}
                        </button>
                      </div>
                      {showParams ? (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          className="rounded-lg bg-background-muted p-4 border border-border"
                        >
                          <pre className="overflow-x-auto text-xs text-text-primary">
                            {JSON.stringify(tool_args, null, 2)}
                          </pre>
                        </motion.div>
                      ) : (
                        <div className="rounded-lg bg-background-muted px-4 py-3 text-sm text-text-secondary border border-border">
                          {Object.keys(tool_args).length} 个参数
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div>
                    <label className="text-sm font-medium text-text-primary mb-2 block">
                      需审批操作（{actionRequests.length}）
                    </label>
                    <div className="space-y-3">
                      {actionRequests.map((action, index) => (
                        <div
                          key={`${action.name}-${index}`}
                          className="rounded-lg border border-border bg-background-muted p-4"
                        >
                          <div className="text-sm font-mono text-text-primary">
                            <Wrench className="w-4 h-4 inline mr-2 text-primary" />
                            {action.name}
                          </div>
                          <pre className="mt-3 overflow-x-auto text-xs text-text-secondary">
                            {JSON.stringify(action.args, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Warning */}
                <div className="rounded-lg bg-warning-bg border border-warning-text/20 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-warning-text flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-warning-text">
                      <span className="font-semibold">⚠️ 不可逆操作警告：</span>
                      此操作执行后无法撤回。请确认参数无误后再继续。
                    </p>
                  </div>
                </div>

                {canGrantSession && grantTargetTool ? (
                  <label className="flex items-start gap-3 rounded-lg border border-border bg-background-muted px-4 py-3">
                    <input
                      type="checkbox"
                      checked={grantSession}
                      onChange={(event) => setGrantSession(event.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                      aria-label="本会话内不再询问此工具"
                    />
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-text-primary">本会话内不再询问此工具</div>
                      <p className="text-xs text-text-secondary">
                        后续在当前会话再次调用 <span className="font-mono">{grantTargetTool}</span> 时将直接放行，
                        你仍可在右侧上下文面板或移动端会话栏中随时撤销。
                      </p>
                    </div>
                  </label>
                ) : (
                  <div className="rounded-lg border border-border bg-background-muted px-4 py-3 text-xs text-text-secondary">
                    本次审批包含多个工具类型，不能一次性设置“本会话自动放行”。
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-border p-6">
                <div className="flex justify-end gap-3">
                  <button
                    onClick={handleCancel}
                    className="rounded-xl border border-border px-5 py-2.5 text-sm font-medium text-text-primary
                           transition-all hover:bg-background hover:shadow-md"
                  >
                    <XIcon className="w-4 h-4 inline mr-2" />
                    取消操作
                  </button>
                  <button
                    onClick={handleConfirm}
                    className="rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white
                           transition-all hover:bg-danger/90 hover:shadow-md flex items-center gap-2"
                  >
                    <Check className="w-4 h-4" />
                    确认执行
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
