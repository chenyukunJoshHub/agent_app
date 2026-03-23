/**
 * Skill types.
 *
 * Types for the Skills UI components.
 */

/**
 * Single skill response from the backend.
 */
export interface Skill {
  /** Skill name */
  name: string;
  /** Skill description (trigger conditions + capabilities) */
  description: string;
  /** File path to SKILL.md */
  file_path: string;
  /** Required tools for this skill */
  tools: string[];
}

/**
 * Skills list response.
 */
export interface SkillsListResponse {
  /** List of available skills */
  skills: Skill[];
}

/**
 * Extended skill type with additional UI state.
 */
export interface SkillWithStatus extends Skill {
  /** Whether this skill is currently active in the session */
  isActive?: boolean;
}
