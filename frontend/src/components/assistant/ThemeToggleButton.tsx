'use client';

import { MoonStar, Sun } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { ThemeMode } from '@/store/theme';

interface ThemeToggleButtonProps {
  theme: ThemeMode;
  onToggle: () => void;
  className?: string;
}

export function ThemeToggleButton({ theme, onToggle, className }: ThemeToggleButtonProps) {
  const nextIsDark = theme === 'light';
  const ariaLabel = nextIsDark ? '切换为暗色主题' : '切换为亮色主题';

  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium',
        'border-border bg-bg-card/75 text-text-secondary backdrop-blur-md',
        'hover:bg-bg-card hover:text-text-primary transition-colors duration-200',
        className,
      )}
    >
      {nextIsDark ? <MoonStar className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      <span>{nextIsDark ? '暗色' : '亮色'}</span>
    </button>
  );
}
