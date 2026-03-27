/**
 * AssistantComposer — input area using assistant-ui's composer runtime.
 *
 * Integrates the existing useSkillCommand dropdown for /skill autocomplete.
 * Uses ComposerPrimitive.Root + ComposerPrimitive.Send for structure,
 * with a custom textarea for full control over the skill command UI.
 */
'use client';

import { useState, KeyboardEvent, useRef, useEffect, useCallback } from 'react';
import {
  ComposerPrimitive,
  useComposerRuntime,
  useComposer,
  useThread,
  useThreadRuntime,
} from '@assistant-ui/react';
import { ArrowUp, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSkillCommand } from '@/hooks/useSkillCommand';

export function AssistantComposer() {
  const runtime = useComposerRuntime();
  const text = useComposer((s) => s.text);
  const isRunning = useThread((s) => s.isRunning);

  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { isOpen, filtered, onInputChange, onSelect, onClose } = useSkillCommand();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 220);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [text]);

  useEffect(() => {
    if (isOpen) setHighlightedIndex(0);
  }, [isOpen, filtered]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      runtime.setText(value);
      onInputChange(value);
    },
    [runtime, onInputChange]
  );

  const handleSelectSkill = useCallback(
    (index: number) => {
      const skill = filtered[index];
      if (!skill) return;
      const newValue = onSelect(skill);
      runtime.setText(newValue);
      onInputChange(newValue);
      textareaRef.current?.focus();
    },
    [filtered, onSelect, onInputChange, runtime]
  );

  const handleSend = useCallback(() => {
    if (!text.trim() || isRunning) return;
    runtime.send();
    onClose();
  }, [text, isRunning, runtime, onClose]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (isOpen) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setHighlightedIndex((i) => Math.min(i + 1, filtered.length - 1));
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setHighlightedIndex((i) => Math.max(i - 1, 0));
          return;
        }
        if (e.key === 'Enter' || e.key === 'Tab') {
          e.preventDefault();
          handleSelectSkill(highlightedIndex);
          return;
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          onClose();
          return;
        }
      }

      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [isOpen, filtered.length, highlightedIndex, handleSelectSkill, handleSend, onClose]
  );

  const threadRuntime = useThreadRuntime();
  const canSend = text.trim().length > 0 && !isRunning;

  return (
    <ComposerPrimitive.Root className="border-border/35 bg-transparent px-4 pb-4 pt-3 md:px-8 md:pb-6">
      <div className="mx-auto w-full max-w-5xl">
        <div className="relative">
          {isOpen && filtered.length > 0 && (
            <div className="absolute bottom-full left-0 z-50 mb-2 max-h-72 w-full overflow-y-auto rounded-3xl border border-border/70 bg-bg-card/95 p-2 shadow-[0_18px_48px_var(--color-shadow-soft)] backdrop-blur-xl">
              {filtered.map((skill, index) => (
                <button
                  key={skill.name}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelectSkill(index);
                  }}
                  className={cn(
                    'flex w-full items-start gap-2 rounded-2xl px-4 py-2.5 text-left transition-colors',
                    index === highlightedIndex
                      ? 'bg-primary/15 text-primary'
                      : 'text-text-primary hover:bg-bg-muted/70'
                  )}
                >
                  <span className="shrink-0 font-mono text-sm font-semibold">/{skill.name}</span>
                  <span className="truncate text-xs text-text-muted">
                    {skill.description.slice(0, 68)}
                    {skill.description.length > 68 ? '…' : ''}
                  </span>
                </button>
              ))}
            </div>
          )}

          <div className="rounded-[36px] border border-border/60 bg-bg-card/80 px-5 pb-4 pt-4 shadow-[0_22px_56px_var(--color-shadow-soft)] backdrop-blur-xl">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="描述任务或输入 / 选择技能..."
              className={cn(
                'w-full resize-none border-none bg-transparent px-2 py-1 text-lg text-text-primary',
                'placeholder:text-text-muted',
                'focus:outline-none',
                'disabled:cursor-not-allowed disabled:opacity-60',
                'min-h-[74px] max-h-[220px]'
              )}
              rows={1}
              disabled={isRunning}
            />

            <div className="mt-4 flex justify-end">
              {isRunning ? (
                <button
                  type="button"
                  onClick={() => threadRuntime.cancelRun()}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-full',
                    'border border-border bg-bg-card text-text-muted',
                    'transition-all duration-200 hover:bg-bg-muted hover:text-text-primary',
                  )}
                  aria-label="停止生成"
                >
                  <Square className="h-4 w-4" fill="currentColor" />
                </button>
              ) : (
                <ComposerPrimitive.Send
                  asChild
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-full transition-all duration-200',
                    canSend
                      ? 'bg-primary text-white shadow-[0_10px_22px_rgba(66,133,244,0.4)] hover:bg-primary-hover'
                      : 'border border-border bg-bg-card text-text-muted',
                  )}
                >
                  <button disabled={!canSend} aria-label="发送">
                    <ArrowUp className="h-4 w-4" />
                  </button>
                </ComposerPrimitive.Send>
              )}
            </div>
          </div>
        </div>

        {/* <p className="mt-3 text-center text-xs text-text-muted">
          Gemini may display inaccurate info, including about people, so double-check its responses.
        </p> */}
      </div>
    </ComposerPrimitive.Root>
  );
}
