/**
 * useContextWindow Hook
 *
 * Manages Context Window data fetching and SSE event updates.
 * Integrates with useSession store for state management.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSession } from '@/store/use-session';
import { getSessionContextUrl } from '@/lib/api-config';
import type {
  ContextWindowData,
  SlotUsage,
  TokenBudgetState,
  SlotAllocation,
} from '@/types/context-window';
import { SLOT_COLORS, SLOT_DISPLAY_NAMES } from '@/types/context-window';

/**
 * Convert backend slot allocation to frontend slot usage
 */
function convertToSlotUsage(slots: SlotAllocation): SlotUsage[] {
  return (Object.entries(slots) as [keyof SlotAllocation, number][]).map(
    ([name, allocated]) => ({
      name,
      displayName: SLOT_DISPLAY_NAMES[name],
      allocated,
      used: 0, // P0: No actual usage tracking yet
      color: SLOT_COLORS[name],
    })
  );
}

/**
 * Fetch context data from backend API
 */
async function fetchContextData(sessionId: string): Promise<ContextWindowData> {
  const url = getSessionContextUrl(sessionId);
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to fetch context: ${response.statusText}`);
  }

  const data = await response.json();

  // Convert backend response to ContextWindowData
  const budget: TokenBudgetState = data.token_budget;
  const slotUsage = convertToSlotUsage(budget.slots);

  return {
    budget,
    slotUsage,
    compressionEvents: [], // P0: No compression events yet
  };
}

/**
 * useContextWindow Hook
 *
 * Provides Context Window data and update functions.
 * Automatically fetches initial data and updates on SSE events.
 */
export function useContextWindow() {
  const { sessionId } = useSession();
  const [data, setData] = useState<ContextWindowData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch initial context data
   */
  const fetchContext = useCallback(async () => {
    if (!sessionId) return;

    setIsLoading(true);
    setError(null);

    try {
      const contextData = await fetchContextData(sessionId);
      setData(contextData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch context');
      console.error('[useContextWindow] Fetch error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  /**
   * Update slot usage (called from SSE events)
   */
  const updateSlotUsage = useCallback((slotName: keyof SlotAllocation, used: number) => {
    setData((prev) => {
      if (!prev) return prev;

      return {
        ...prev,
        slotUsage: prev.slotUsage.map((slot) =>
          slot.name === slotName ? { ...slot, used } : slot
        ),
      };
    });
  }, []);

  /**
   * Add compression event
   */
  const addCompressionEvent = useCallback(
    (event: {
      before_tokens: number;
      after_tokens: number;
      method: 'summarization' | 'truncation' | 'hybrid';
      affected_slots: string[];
    }) => {
      setData((prev) => {
        if (!prev) return prev;

        const tokens_saved = event.before_tokens - event.after_tokens;

        const newEvent = {
          id: `compression_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: Date.now(),
          ...event,
          tokens_saved,
        };

        return {
          ...prev,
          compressionEvents: [newEvent, ...prev.compressionEvents],
        };
      });
    },
    []
  );

  /**
   * Update total usage (called from SSE token_update events)
   */
  const updateTotalUsage = useCallback((totalUsed: number) => {
    setData((prev) => {
      if (!prev) return prev;

      const totalRemaining = prev.budget.working_budget - totalUsed;

      return {
        ...prev,
        budget: {
          ...prev.budget,
          usage: {
            ...prev.budget.usage,
            total_used: totalUsed,
            total_remaining: Math.max(0, totalRemaining),
          },
        },
      };
    });
  }, []);

  // Fetch initial data when session changes
  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchContext,
    updateSlotUsage,
    addCompressionEvent,
    updateTotalUsage,
  };
}
