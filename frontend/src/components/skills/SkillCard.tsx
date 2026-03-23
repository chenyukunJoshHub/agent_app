'use client';

import { motion } from 'framer-motion';
import { BookOpen, Wrench, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SkillWithStatus } from '@/types/skills';

interface SkillCardProps {
  skill: SkillWithStatus;
  onClick: () => void;
  index: number;
}

export function SkillCard({ skill, onClick, index }: SkillCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      onClick={onClick}
      className={cn(
        'relative rounded-lg border bg-background-card p-4 shadow-sm',
        'cursor-pointer transition-all duration-200',
        'hover:shadow-md hover:border-primary/50',
        'active:scale-[0.98]'
      )}
      data-testid={`skill-card-${skill.name}`}
    >
      {/* Active Badge */}
      {skill.isActive && (
        <div className="absolute top-3 right-3">
          <span
            className={cn(
              'flex items-center gap-1 rounded-full px-2 py-1',
              'bg-success-bg text-success-text',
              'text-xs font-semibold'
            )}
          >
            <CheckCircle2 className="w-3 h-3" />
            ACTIVE
          </span>
        </div>
      )}

      {/* Skill Header */}
      <div className="mb-3">
        <h3 className="font-semibold text-text-primary text-base mb-2 pr-16">
          {skill.name}
        </h3>
        <p className="text-sm text-text-secondary line-clamp-3 leading-relaxed">
          {skill.description}
        </p>
      </div>

      {/* Skill Footer */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        {/* File Path */}
        <div className="flex items-center gap-1.5">
          <BookOpen className="w-3.5 h-3.5" />
          <span className="font-mono">{skill.file_path}</span>
        </div>

        {/* Tools */}
        {skill.tools && skill.tools.length > 0 && (
          <div className="flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5" />
            <span>{skill.tools.length} tool{skill.tools.length !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      {/* Hover overlay */}
      <div className="absolute inset-0 rounded-lg bg-primary/5 opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none" />
    </motion.div>
  );
}
