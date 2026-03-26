'use client';

import { useState, useCallback, useRef } from 'react';
import { getSkillsUrl } from '@/lib/api-config';

export interface Skill {
  name: string;
  description: string;
}

export type InvocationMode = 'hint' | 'force';

export interface UseSkillCommandReturn {
  isOpen: boolean;
  filtered: Skill[];
  selectedMode: InvocationMode;
  setMode: (mode: InvocationMode) => void;
  onInputChange: (value: string) => Promise<void>;
  onSelect: (skill: Skill) => string;
  onClose: () => void;
}

export function useSkillCommand(): UseSkillCommandReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [filtered, setFiltered] = useState<Skill[]>([]);
  const [selectedMode, setMode] = useState<InvocationMode>('hint');
  const skillsCache = useRef<Skill[] | null>(null);

  const fetchSkills = useCallback(async (): Promise<Skill[]> => {
    if (skillsCache.current !== null) return skillsCache.current;
    try {
      const res = await fetch(getSkillsUrl());
      if (!res.ok) return [];
      const data = await res.json() as { skills: Skill[] };
      skillsCache.current = data.skills ?? [];
      return skillsCache.current;
    } catch {
      return [];
    }
  }, []);

  const onInputChange = useCallback(async (value: string) => {
    if (!value.startsWith('/')) {
      setIsOpen(false);
      setFiltered([]);
      return;
    }
    const prefix = value.slice(1).toLowerCase(); // strip leading '/'
    const all = await fetchSkills();
    const matches = all.filter((s) => s.name.toLowerCase().startsWith(prefix));
    setFiltered(matches);
    setIsOpen(matches.length > 0);
  }, [fetchSkills]);

  const onSelect = useCallback((skill: Skill): string => {
    setIsOpen(false);
    return `/${skill.name} `;
  }, []);

  const onClose = useCallback(() => {
    setIsOpen(false);
  }, []);

  return { isOpen, filtered, selectedMode, setMode, onInputChange, onSelect, onClose };
}
