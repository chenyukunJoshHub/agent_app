import { describe, expect, it, vi } from 'vitest';

import type { Skill } from '@/hooks/useSkillCommand';
import { loadSkillsWithFallback } from '@/hooks/useSkillCommand';

function jsonResponse(payload: unknown, ok = true) {
  return {
    ok,
    json: async () => payload,
  } as Response;
}

describe('loadSkillsWithFallback', () => {
  it('falls back to /api/skills when preferred URL request fails', async () => {
    const skills: Skill[] = [{ name: 'agent-browser', description: 'browser automation' }];
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(jsonResponse({ skills }));

    const loaded = await loadSkillsWithFallback(
      fetchMock as unknown as typeof fetch,
      'http://localhost:8000/skills/',
    );

    expect(loaded).toEqual(skills);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://localhost:8000/skills/');
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/skills');
  });

  it('does not duplicate fallback call when preferred URL is already /api/skills/', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ skills: [] }));

    await loadSkillsWithFallback(fetchMock as unknown as typeof fetch, '/api/skills/');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/skills/');
  });

  it('does not duplicate fallback call when preferred URL is already /api/skills', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ skills: [] }));

    await loadSkillsWithFallback(fetchMock as unknown as typeof fetch, '/api/skills');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/api/skills');
  });
});
