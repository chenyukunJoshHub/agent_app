"use client";

import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-background-alt p-4 transition-colors duration-300">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述任务，例如：帮我查一下茅台今天的股价..."
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
          {/* 字符计数 */}
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
