'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getSkillsUrl } from '@/lib/api-config';
import type { Skill, SkillWithStatus } from '@/types/skills';
import { SkillCard } from './SkillCard';
import { SkillDetail } from './SkillDetail';

interface SkillPanelProps {
  className?: string;
}

export function SkillPanel({ className }: SkillPanelProps) {
  const [skills, setSkills] = useState<SkillWithStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Fetch skills on mount
  useEffect(() => {
    const fetchSkills = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(getSkillsUrl());

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setSkills(data.skills || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch skills');
        console.error('Error fetching skills:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSkills();
  }, []);

  const handleSkillClick = (skill: SkillWithStatus) => {
    setSelectedSkill(skill);
    setIsDetailOpen(true);
  };

  const handleCloseDetail = () => {
    setIsDetailOpen(false);
    // Delay clearing the selected skill for animation
    setTimeout(() => setSelectedSkill(null), 300);
  };

  return (
    <div className={cn('flex h-full flex-col', className)} data-testid="skill-panel">
      {/* Header */}
      <div className="border-b border-border p-6 bg-background-alt">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2">
            <Sparkles className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="font-semibold text-text-primary text-lg">Skills</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {!isLoading && !error && `${skills.length} available skill${skills.length !== 1 ? 's' : ''}`}
              {isLoading && 'Loading skills...'}
              {error && 'Failed to load skills'}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-48">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Loading skills...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-6">
            <div className="rounded-lg bg-error-bg text-error-text p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-sm">Failed to load skills</p>
                <p className="text-sm mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !error && skills.length === 0 && (
          <div className="flex items-center justify-center h-48">
            <div className="text-center">
              <Sparkles className="w-12 h-12 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No skills available</p>
            </div>
          </div>
        )}

        {!isLoading && !error && skills.length > 0 && (
          <div className="p-6">
            <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
              {skills.map((skill, index) => (
                <SkillCard
                  key={skill.name}
                  skill={skill}
                  onClick={() => handleSkillClick(skill)}
                  index={index}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Detail Drawer */}
      <SkillDetail
        skill={selectedSkill}
        isOpen={isDetailOpen}
        onClose={handleCloseDetail}
      />
    </div>
  );
}
