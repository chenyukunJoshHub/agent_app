/**
 * Unit tests for useSession store.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useSession } from "@/store/use-session";

describe("useSession", () => {
  beforeEach(() => {
    // Reset store state before each test
    useSession.getState().clearMessages();
  });

  describe("initial state", () => {
    it("has empty messages array", () => {
      const state = useSession.getState();
      expect(state.messages).toEqual([]);
    });

    it("has default session_id", () => {
      const state = useSession.getState();
      expect(state.sessionId).toMatch(/^session_\d+$/);
    });

    it("has default user_id", () => {
      const state = useSession.getState();
      expect(state.userId).toBe("dev_user");
    });

    it("has isLoading false", () => {
      const state = useSession.getState();
      expect(state.isLoading).toBe(false);
    });

    it("has null error", () => {
      const state = useSession.getState();
      expect(state.error).toBeNull();
    });
  });

  describe("addMessage", () => {
    it("adds user message", () => {
      const { addMessage } = useSession.getState();

      addMessage({
        role: "user",
        content: "Hello",
      });

      const messages = useSession.getState().messages;
      expect(messages).toHaveLength(1);
      expect(messages[0].role).toBe("user");
      expect(messages[0].content).toBe("Hello");
    });

    it("adds assistant message", () => {
      const { addMessage } = useSession.getState();

      addMessage({
        role: "assistant",
        content: "Hi there!",
      });

      const messages = useSession.getState().messages;
      expect(messages).toHaveLength(1);
      expect(messages[0].role).toBe("assistant");
    });

    it("generates unique message id", () => {
      const { addMessage } = useSession.getState();

      addMessage({ role: "user", content: "Message 1" });
      addMessage({ role: "user", content: "Message 2" });

      const messages = useSession.getState().messages;
      expect(messages[0].id).not.toBe(messages[1].id);
    });

    it("generates timestamp for message", () => {
      const { addMessage } = useSession.getState();

      const before = Date.now();
      addMessage({ role: "user", content: "Test" });
      const after = Date.now();

      const messages = useSession.getState().messages;
      expect(messages[0].timestamp).toBeGreaterThanOrEqual(before);
      expect(messages[0].timestamp).toBeLessThanOrEqual(after);
    });

    it("adds message with tool_calls", () => {
      const { addMessage } = useSession.getState();

      addMessage({
        role: "assistant",
        content: "Searching...",
        tool_calls: [
          {
            id: "tc_1",
            tool_name: "web_search",
            args: { query: "test" },
            status: "pending" as const,
          },
        ],
      });

      const messages = useSession.getState().messages;
      expect(messages[0].tool_calls).toHaveLength(1);
      expect(messages[0].tool_calls?.[0].tool_name).toBe("web_search");
    });
  });

  describe("updateToolCall", () => {
    it("updates tool call status", () => {
      const { addMessage, updateToolCall } = useSession.getState();

      // Add message with tool call
      addMessage({
        role: "assistant",
        content: "Test",
        tool_calls: [
          {
            id: "tc_1",
            tool_name: "web_search",
            args: {},
            status: "pending" as const,
          },
        ],
      });

      const messageId = useSession.getState().messages[0].id;

      // Update tool call
      updateToolCall(messageId, "tc_1", { status: "completed" as const });

      const messages = useSession.getState().messages;
      expect(messages[0].tool_calls?.[0].status).toBe("completed");
    });

    it("updates tool call result", () => {
      const { addMessage, updateToolCall } = useSession.getState();

      addMessage({
        role: "assistant",
        content: "Test",
        tool_calls: [
          {
            id: "tc_1",
            tool_name: "web_search",
            args: {},
            status: "running" as const,
          },
        ],
      });

      const messageId = useSession.getState().messages[0].id;

      updateToolCall(messageId, "tc_1", {
        result: "Search results",
      });

      const messages = useSession.getState().messages;
      expect(messages[0].tool_calls?.[0].result).toBe("Search results");
    });

    it("does not affect other tool calls", () => {
      const { addMessage, updateToolCall } = useSession.getState();

      addMessage({
        role: "assistant",
        content: "Test",
        tool_calls: [
          { id: "tc_1", tool_name: "web_search", args: {}, status: "pending" as const },
          { id: "tc_2", tool_name: "fetch", args: {}, status: "pending" as const },
        ],
      });

      const messageId = useSession.getState().messages[0].id;

      updateToolCall(messageId, "tc_1", { status: "completed" as const });

      const messages = useSession.getState().messages;
      expect(messages[0].tool_calls?.[0].status).toBe("completed");
      expect(messages[0].tool_calls?.[1].status).toBe("pending");
    });
  });

  describe("setLoading", () => {
    it("sets isLoading to true", () => {
      const { setLoading } = useSession.getState();

      setLoading(true);

      expect(useSession.getState().isLoading).toBe(true);
    });

    it("sets isLoading to false", () => {
      const { setLoading } = useSession.getState();

      setLoading(true);
      setLoading(false);

      expect(useSession.getState().isLoading).toBe(false);
    });
  });

  describe("setError", () => {
    it("sets error message", () => {
      const { setError } = useSession.getState();

      setError("Something went wrong");

      expect(useSession.getState().error).toBe("Something went wrong");
    });

    it("clears error with null", () => {
      const { setError } = useSession.getState();

      setError("Error");
      setError(null);

      expect(useSession.getState().error).toBeNull();
    });
  });

  describe("setSessionId", () => {
    it("updates session_id", () => {
      const { setSessionId } = useSession.getState();

      setSessionId("custom_session_123");

      expect(useSession.getState().sessionId).toBe("custom_session_123");
    });
  });

  describe("clearMessages", () => {
    it("clears all messages", () => {
      const { addMessage, clearMessages } = useSession.getState();

      addMessage({ role: "user", content: "Test 1" });
      addMessage({ role: "user", content: "Test 2" });

      clearMessages();

      expect(useSession.getState().messages).toEqual([]);
    });
  });

  describe("store immutability", () => {
    it("does not mutate existing state when adding message", () => {
      const { addMessage } = useSession.getState();

      const beforeMessages = useSession.getState().messages;
      addMessage({ role: "user", content: "Test" });

      expect(beforeMessages).toEqual([]);
      expect(useSession.getState().messages).toHaveLength(1);
    });
  });

  describe("Turn tracking", () => {
    it("初始 turnCounter 为 0，currentTurnId 为 null", () => {
      const state = useSession.getState();
      expect(state.turnCounter).toBe(0);
      expect(state.currentTurnId).toBeNull();
    });

    it("incrementTurn 后 turnCounter+1，currentTurnId 更新", () => {
      useSession.getState().incrementTurn();
      const state = useSession.getState();
      expect(state.turnCounter).toBe(1);
      expect(state.currentTurnId).toBe('turn_1');
    });

    it("clearMessages 重置 turnCounter 和 currentTurnId", () => {
      useSession.getState().incrementTurn();
      useSession.getState().clearMessages();
      const state = useSession.getState();
      expect(state.turnCounter).toBe(0);
      expect(state.currentTurnId).toBeNull();
    });

    it("addTraceEvent 自动打上 currentTurnId", () => {
      useSession.getState().incrementTurn();
      useSession.getState().addTraceEvent({
        id: 'e1', timestamp: new Date().toISOString(),
        stage: 'react', step: 'start', status: 'start', payload: {},
      });
      const { traceEvents } = useSession.getState();
      expect(traceEvents[0].turnId).toBe('turn_1');
    });
  });

  describe("stateMessages", () => {
    it("初始 stateMessages 为空数组", () => {
      expect(useSession.getState().stateMessages).toEqual([]);
    });

    it("setStateMessages 更新 stateMessages", () => {
      useSession.getState().setStateMessages([
        { role: 'user', content: 'hello' },
      ]);
      expect(useSession.getState().stateMessages).toHaveLength(1);
    });

    it("clearMessages 重置 stateMessages", () => {
      useSession.getState().setStateMessages([{ role: 'user', content: 'hi' }]);
      useSession.getState().clearMessages();
      expect(useSession.getState().stateMessages).toEqual([]);
    });
  });
});
