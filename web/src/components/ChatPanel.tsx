import { type Ref, useState } from 'react';

import type { ChatMessage } from '../types/api';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => void;
  onStartSession: (query: string) => void;
  isSessionActive: boolean;
  hasSession: boolean;
  isBusy: boolean;
  inputRef?: Ref<HTMLInputElement>;
  isFocused?: boolean;
}

export function ChatPanel({
  messages,
  onSendMessage,
  onStartSession,
  isSessionActive,
  hasSession,
  isBusy,
  inputRef,
  isFocused = false,
}: ChatPanelProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim()) return;

    if (!isSessionActive && hasSession && messages.length === 0) {
      onStartSession(input);
    } else {
      onSendMessage(input);
    }
    setInput('');
  };

  return (
    <div className="chat-panel" data-focus-active={isFocused ? 'true' : 'false'}>
      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message role-${msg.role}`}>
            <div className="message-role">{msg.role}</div>
            <div className="message-text">{msg.text}</div>
          </div>
        ))}
      </div>
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={hasSession ? 'Type a message...' : 'Create a session first'}
          disabled={!hasSession || isBusy}
          className="chat-input"
        />
        <button
          type="submit"
          disabled={!hasSession || !input.trim() || isBusy}
          className="btn-primary"
        >
          Send
        </button>
      </form>
    </div>
  );
}
