/**
 * Unit tests for ChatInput component.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "@/components/ChatInput";

describe("ChatInput", () => {
  it("renders textarea and send button", () => {
    render(<ChatInput onSend={vi.fn()} />);

    expect(screen.getByPlaceholderText(/描述任务/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /发送/i })).toBeInTheDocument();
  });

  it("disables send button when input is empty", () => {
    render(<ChatInput onSend={vi.fn()} />);

    const sendButton = screen.getByRole("button", { name: /发送/i });
    expect(sendButton).toBeDisabled();
  });

  it("enables send button when input has text", () => {
    render(<ChatInput onSend={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/描述任务/);
    const sendButton = screen.getByRole("button", { name: /发送/i });

    fireEvent.change(textarea, { target: { value: "test message" } });

    expect(sendButton).not.toBeDisabled();
  });

  it("calls onSend with message when send button clicked", async () => {
    const user = userEvent.setup();
    const mockSend = vi.fn();

    render(<ChatInput onSend={mockSend} />);

    const textarea = screen.getByPlaceholderText(/描述任务/);
    const sendButton = screen.getByRole("button", { name: /发送/i });

    await user.type(textarea, "test message");
    await user.click(sendButton);

    expect(mockSend).toHaveBeenCalledWith("test message");
  });

  it("calls onSend when Enter key pressed (without Shift)", async () => {
    const user = userEvent.setup();
    const mockSend = vi.fn();

    render(<ChatInput onSend={mockSend} />);

    const textarea = screen.getByPlaceholderText(/描述任务/);

    await user.type(textarea, "test message");
    await user.keyboard("{Enter}");

    expect(mockSend).toHaveBeenCalledWith("test message");
  });

  it("does not call onSend when Shift+Enter pressed", async () => {
    const user = userEvent.setup();
    const mockSend = vi.fn();

    render(<ChatInput onSend={mockSend} />);

    const textarea = screen.getByPlaceholderText(/描述任务/);

    await user.type(textarea, "test message");
    await user.keyboard("{Shift>}{Enter}{/Shift}");

    expect(mockSend).not.toHaveBeenCalled();
  });

  it("clears input after sending", async () => {
    const user = userEvent.setup();
    const mockSend = vi.fn();

    render(<ChatInput onSend={mockSend} />);

    const textarea = screen.getByPlaceholderText(/描述任务/) as HTMLTextAreaElement;

    await user.type(textarea, "test message");
    await user.click(screen.getByRole("button", { name: /发送/i }));

    expect(textarea.value).toBe("");
  });

  it("shows '发送中...' when disabled", () => {
    render(<ChatInput onSend={vi.fn()} disabled={true} />);

    expect(screen.getByRole("button", { name: /发送中/i })).toBeInTheDocument();
  });

  it("trims whitespace before sending", async () => {
    const user = userEvent.setup();
    const mockSend = vi.fn();

    render(<ChatInput onSend={mockSend} />);

    const textarea = screen.getByPlaceholderText(/描述任务/);

    await user.type(textarea, "  test message  ");
    await user.click(screen.getByRole("button", { name: /发送/i }));

    expect(mockSend).toHaveBeenCalledWith("test message");
  });
});
