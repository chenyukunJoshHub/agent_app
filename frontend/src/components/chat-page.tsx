/**
 * Main Chat Page Component
 */

'use client';

import { useState } from 'react';
import { useChatStore } from '@/store/use-chat-store';
import { Send, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ChatPage() {
  const { messages, sendMessage, isProcessing, timelineEvents } = useChatStore();
  const [input, setInput] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const message = input.trim();
    setInput('');
    await sendMessage(message);
  };

  return (
    <div className="flex h-screen w-full">
      {/* Left Sidebar - Sessions */}
      <aside className="w-[272px] border-r bg-surface flex flex-col">
        <div className="p-4 border-b">
          <h1 className="font-semibold text-lg">Multi-Tool Agent</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <p className="text-sm text-textMuted">No sessions yet</p>
        </div>
      </aside>

      {/* Center - Chat Area */}
      <main className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.length === 0 ? (
              <div className="text-center text-textMuted py-20">
                <p className="text-lg">Start a conversation with the AI Agent</p>
                <p className="text-sm mt-2">
                  The agent can use tools, remember context, and show its reasoning
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    'flex',
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[80%] rounded-2xl px-5 py-3',
                      message.role === 'user'
                        ? 'bg-accent text-white rounded-br-md'
                        : 'bg-surfaceMuted text-text rounded-bl-md'
                    )}
                  >
                    <p className="whitespace-pre-wrap break-words">
                      {message.content}
                    </p>
                    {message.tokens_used && (
                      <p className="text-xs opacity-70 mt-1">
                        {message.tokens_used} tokens
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
            {isProcessing && (
              <div className="flex justify-start">
                <div className="bg-surfaceMuted rounded-2xl rounded-bl-md px-5 py-3 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm text-textMuted">Agent is thinking...</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your message..."
                disabled={isProcessing}
                className="flex-1 px-4 py-3 rounded-lg border bg-surface focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isProcessing || !input.trim()}
                className="px-5 py-3 bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isProcessing ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
                <span>Send</span>
              </button>
            </div>
          </form>
        </div>
      </main>

      {/* Right Sidebar - Timeline */}
      <aside className="w-[356px] border-l bg-surface flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">Reasoning Timeline</h2>
        </div>
        <Timeline events={timelineEvents} />
      </aside>
    </div>
  );
}

function Timeline({ events }: { events: Array<{ type: string; data: unknown; timestamp: string }> }) {
  if (events.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-sm text-textMuted">
          Agent reasoning will appear here as it processes your requests
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-border" />

        {/* Events */}
        <div className="space-y-4">
          {events.map((event, index) => (
            <div key={index} className="relative flex gap-3">
              {/* Timeline dot */}
              <div className="w-4 h-4 rounded-full bg-accent border-2 border-background z-10 flex-shrink-0 mt-0.5" />

              {/* Event content */}
              <div className="flex-1 min-w-0">
                <div className="text-xs text-textMuted mb-1">
                  {formatEventType(event.type)}
                </div>
                <EventContent type={event.type} data={event.data} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function formatEventType(type: string): string {
  const labels: Record<string, string> = {
    start: 'Started',
    thinking: 'Thinking',
    tool_call: 'Tool Call',
    tool_result: 'Tool Result',
    hil_request: 'Confirmation Required',
    response: 'Response',
    end: 'Completed',
    error: 'Error',
  };
  return labels[type] || type;
}

function EventContent({ type, data }: { type: string; data: unknown }) {
  const content = JSON.stringify(data, null, 2);

  return (
    <div className="bg-surfaceMuted rounded-lg p-3">
      {type === 'tool_call' && (
        <div>
          <div className="text-xs font-mono text-accent mb-1">
            {(data as { tool?: string })?.tool}
          </div>
          <pre className="text-xs text-textMuted overflow-x-auto">
            {content}
          </pre>
        </div>
      )}
      {type === 'thinking' && (
        <p className="text-sm text-textMuted">
          {(data as { content?: string })?.content}
        </p>
      )}
      {type === 'response' && (
        <p className="text-sm">{(data as { content?: string })?.content}</p>
      )}
      {type === 'error' && (
        <p className="text-sm text-red-500">
          {(data as { error?: string })?.error}
        </p>
      )}
    </div>
  );
}
