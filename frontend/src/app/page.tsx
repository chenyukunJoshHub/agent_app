export default function HomePage() {
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
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <div className="text-center text-textMuted py-20">
              <p className="text-lg">Start a conversation with the AI Agent</p>
              <p className="text-sm mt-2">
                The agent can use tools, remember context, and show its reasoning
              </p>
            </div>
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t p-4">
          <div className="max-w-3xl mx-auto">
            <input
              type="text"
              placeholder="Type your message..."
              className="w-full px-4 py-3 rounded-lg border bg-surface focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        </div>
      </main>

      {/* Right Sidebar - Timeline */}
      <aside className="w-[356px] border-l bg-surface flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">Reasoning Timeline</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <p className="text-sm text-textMuted">
            Agent reasoning will appear here as it processes your requests
          </p>
        </div>
      </aside>
    </div>
  );
}
