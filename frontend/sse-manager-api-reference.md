# SSE Manager API Reference

## Quick Reference

### Imports
```typescript
import { sseManager, SSEManager, ConnectionState, ConnectionOptions } from '@/lib/sse-manager';
```

### Connection Management

#### `connect(url, options)`
Connect to SSE endpoint.
```typescript
sseManager.connect('http://localhost:8000/chat', {
  message: 'user message',
  session_id: 'session_123',
  user_id: 'user_456',
});
```

#### `disconnect()`
Disconnect and reset state.
```typescript
sseManager.disconnect();
```

#### `isConnected()`
Check if currently connected.
```typescript
if (sseManager.isConnected()) {
  console.log('Connection active');
}
```

### Event Handling

#### `on(eventType, handler)`
Register event handler.
```typescript
sseManager.on('thought', (event) => {
  console.log('Thinking:', event.data);
});
```

#### `off(eventType, handler)`
Unregister event handler.
```typescript
const handler = (event) => console.log(event.data);
sseManager.on('thought', handler);
sseManager.off('thought', handler);
```

### State Management

#### `onStateChange(handler)`
Listen for state changes.
```typescript
sseManager.onStateChange((state: ConnectionState) => {
  console.log('New state:', state);
});
```

#### `offStateChange(handler)`
Stop listening for state changes.
```typescript
const handler = (state) => console.log(state);
sseManager.onStateChange(handler);
sseManager.offStateChange(handler);
```

#### `getState()`
Get current connection state.
```typescript
const state = sseManager.getState(); // 'disconnected' | 'connecting' | 'connected' | 'error'
```

### Custom Configuration

#### Create custom manager instance
```typescript
const customManager = new SSEManager({
  maxReconnectAttempts: 10,
  baseReconnectDelay: 200, // ms
});

customManager.connect(url, options);
```

## Event Types

| Type | Description |
|------|-------------|
| `thought` | Agent reasoning/thinking |
| `tool_start` | Tool invocation started |
| `tool_result` | Tool execution result |
| `hil_interrupt` | Human-in-the-loop interrupt |
| `token_update` | Streaming token update |
| `error` | Error occurred |
| `done` | Agent finished |

## Connection States

| State | Description |
|-------|-------------|
| `disconnected` | Not connected |
| `connecting` | Attempting to connect |
| `connected` | Successfully connected |
| `error` | Connection error occurred |

## Reconnection Behavior

- **Automatic**: Triggers on connection error
- **Exponential Backoff**: 100ms → 200ms → 400ms → 800ms → 1600ms
- **Max Attempts**: 5 (default)
- **Reset**: Attempts reset to 0 on successful connection

## Best Practices

### 1. Always Clean Up
```typescript
// In React component
useEffect(() => {
  return () => {
    sseManager.disconnect();
  };
}, []);
```

### 2. Monitor State Changes
```typescript
sseManager.onStateChange((state) => {
  switch (state) {
    case 'connected':
      // Enable chat input
      break;
    case 'error':
      // Show error message
      break;
    case 'disconnected':
      // Show reconnect button
      break;
  }
});
```

### 3. Handle Errors
```typescript
sseManager.on('error', (event) => {
  console.error('SSE Error:', event.data);
  // Show user-friendly error message
});
```

### 4. Use TypeScript
```typescript
interface ThoughtData {
  content: string;
}

sseManager.on('thought', (event: SSEEvent) => {
  const data = event.data as ThoughtData;
  console.log(data.content);
});
```

## Migration Guide

### From Old Version

The enhanced SSE manager is **100% backward compatible**. No changes required for existing code.

### To Use New Features

1. **Add state monitoring**:
```typescript
sseManager.onStateChange((state) => {
  // Update UI
});
```

2. **Check connection state**:
```typescript
if (sseManager.getState() === 'connected') {
  // Do something
}
```

3. **Customize reconnection** (if needed):
```typescript
const manager = new SSEManager({
  maxReconnectAttempts: 10,
});
```
