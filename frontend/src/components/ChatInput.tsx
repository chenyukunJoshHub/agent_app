"use client";

import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useSkillCommand } from "@/hooks/useSkillCommand";

interface ChatInputProps {
  onSend: (message: string, skillId?: string | null, mode?: string | null) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { isOpen, filtered, selectedMode, onInputChange, onSelect, onClose } =
    useSkillCommand();

  // 自动调整高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  // 下拉列表打开时重置高亮索引
  useEffect(() => {
    if (isOpen) setHighlightedIndex(0);
  }, [isOpen, filtered]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);
    onInputChange(value);
  };

  const handleSelectSkill = (index: number) => {
    const skill = filtered[index];
    if (!skill) return;
    const newValue = onSelect(skill);
    setInput(newValue);
    onInputChange(newValue);
    textareaRef.current?.focus();
  };

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    const match = input.trim().match(/^\/([^\s]+)/);
    const skillId = match ? match[1] : null;
    const mode = skillId ? selectedMode : null;
    onSend(input.trim(), skillId, mode);
    setInput("");
    onClose();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => Math.min(i + 1, filtered.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        handleSelectSkill(highlightedIndex);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-background-alt p-4 transition-colors duration-300">
      <div className="flex items-end gap-3 max-w-4xl mx-auto relative">
        <div className="flex-1 relative">
          {/* 技能下拉列表 */}
          {isOpen && filtered.length > 0 && (
            <div className="absolute bottom-full left-0 mb-1 w-full max-h-60 overflow-y-auto rounded-xl border border-border bg-bg-card shadow-lg z-50">
              {filtered.map((skill, index) => (
                <button
                  key={skill.name}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault(); // 防止 textarea 失焦
                    handleSelectSkill(index);
                  }}
                  className={cn(
                    "w-full px-4 py-2.5 text-left flex items-start gap-2 transition-colors",
                    index === highlightedIndex
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-bg-alt text-text-primary"
                  )}
                >
                  <span className="font-mono font-semibold text-sm shrink-0">
                    /{skill.name}
                  </span>
                  <span className="text-xs text-text-muted truncate">
                    {skill.description.slice(0, 60)}
                    {skill.description.length > 60 ? "…" : ""}
                  </span>
                </button>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="描述任务，或输入 / 选择技能..."
            className={cn(
              "w-full resize-none rounded-xl border border-border",
              "bg-background px-4 py-3 text-sm",
              "placeholder:text-muted-foreground",
              "focus:border-primary focus:ring-2 focus:ring-primary/10",
              "focus:outline-none transition-all duration-200",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "min-h-[48px] max-h-[200px]"
            )}
            rows={1}
            disabled={disabled}
          />
          {input.length > 0 && (
            <div className="absolute bottom-3 right-3 text-xs text-muted-foreground">
              {input.length} 字符
            </div>
          )}
        </div>

        <motion.button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className={cn(
            "rounded-xl bg-primary px-5 py-3",
            "text-sm font-semibold text-white",
            "hover:bg-primary-hover",
            "disabled:bg-muted disabled:cursor-not-allowed",
            "transition-all duration-200",
            "flex items-center gap-2",
            "min-w-[100px]",
            "justify-center"
          )}
          whileHover={{ scale: disabled ? 1 : 1.02 }}
          whileTap={{ scale: disabled ? 1 : 0.98 }}
        >
          {disabled ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              发送中...
            </>
          ) : (
            <>
              发送
              <Send className="w-4 h-4" />
            </>
          )}
        </motion.button>
      </div>
    </div>
  );
}
