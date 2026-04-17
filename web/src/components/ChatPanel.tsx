import { type Ref, useState } from 'react';

import type { ChatMessage } from '../types/api';
import type { SessionStatus } from '../types/api';

const SUPPORTED_MODELS = [
  { id: 'gemini-2.5-computer-use-preview-10-2025', label: 'Gemini 2.5 Computer Use' },
  { id: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview' },
] as const;

const DEFAULT_MODEL = SUPPORTED_MODELS[0].id;

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => void;
  onStartSession: (query: string, modelName: string) => void;
  isSessionActive: boolean;
  hasSession: boolean;
  isBusy: boolean;
  status?: SessionStatus | null;
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
  status = null,
  inputRef,
  isFocused = false,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>(DEFAULT_MODEL);
  const isBeforeStart = hasSession && status === 'idle' && !isSessionActive && messages.length === 0;
  const canSubmit =
    hasSession && !isBusy && (status === 'idle' || status === 'running' || status === 'waiting_for_input');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim()) return;

    if (isBeforeStart) {
      onStartSession(input, selectedModel);
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
      {isBeforeStart && (
        <div className="model-selector-bar">
          <label className="model-selector-label" htmlFor="model-select">Model</label>
          <select
            id="model-select"
            className="model-selector"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {SUPPORTED_MODELS.map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
              </option>
            ))}
          </select>
        </div>
      )}
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            !hasSession
              ? 'Create a session first'
              : status === 'waiting_for_input'
                ? 'Ask a follow-up in the same browser session...'
                : status === 'stopped' || status === 'error'
                  ? 'Close this session and create a new one to continue'
                  : 'Type a message...'
          }
          disabled={!canSubmit}
          className="chat-input"
        />
        <button
          type="submit"
          disabled={!canSubmit || !input.trim()}
          className="btn-primary"
        >
          Send
        </button>
      </form>
    </div>
  );
}
