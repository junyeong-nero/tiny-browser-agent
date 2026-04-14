export type SessionStatus =
  | 'idle'
  | 'running'
  | 'waiting_for_input'
  | 'complete'
  | 'error'
  | 'stopped';

export interface StepAction {
  name: string;
  args: Record<string, unknown>;
}

export interface VerificationItem {
  id: string;
  message: string;
  detail?: string | null;
  run_id?: string | null;
  source_step_id: number | null;
  source_url?: string | null;
  screenshot_path?: string | null;
  html_path?: string | null;
  metadata_path?: string | null;
  a11y_path?: string | null;
  ambiguity_flag?: boolean | null;
  ambiguity_type?: string | null;
  ambiguity_message?: string | null;
  review_evidence?: string[];
  status: 'needs_review' | 'resolved';
}

export interface StepRecord {
  step_id: number;
  run_id?: string | null;
  timestamp: number;
  reasoning: string | null;
  function_calls: StepAction[];
  url: string | null;
  status: 'running' | 'complete' | 'error';
  screenshot_path: string | null;
  html_path: string | null;
  metadata_path: string | null;
  a11y_path?: string | null;
  error_message: string | null;
  phase_id?: string | null;
  phase_label?: string | null;
  phase_summary?: string | null;
  user_visible_label?: string | null;
  ambiguity_flag?: boolean | null;
  ambiguity_type?: string | null;
  ambiguity_message?: string | null;
  review_evidence?: string[];
}

export interface VerificationGroup {
  id: string;
  run_id?: string | null;
  label: string;
  summary?: string | null;
  step_ids: number[];
  steps: StepRecord[];
  screenshot_path?: string | null;
  html_path?: string | null;
  metadata_path?: string | null;
  a11y_path?: string | null;
}

export interface VerificationPayload {
  session_id: string;
  current_run_id?: string | null;
  last_completed_run_id?: string | null;
  request_text?: string | null;
  run_summary?: string | null;
  final_result_summary?: string | null;
  verification_items: VerificationItem[];
  grouped_steps: VerificationGroup[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp: number;
}

export interface SessionSnapshot {
  session_id: string;
  status: SessionStatus;
  current_run_id?: string | null;
  last_completed_run_id?: string | null;
  last_run_status?: 'complete' | 'stopped' | 'error' | null;
  waiting_reason?: 'follow_up' | 'confirmation' | null;
  expires_at?: number | null;
  current_url: string | null;
  latest_screenshot_b64: string | null;
  latest_step_id: number | null;
  last_reasoning: string | null;
  last_actions: StepAction[];
  messages: ChatMessage[];
  final_reasoning: string | null;
  request_text?: string | null;
  run_summary?: string | null;
  verification_items?: VerificationItem[];
  final_result_summary?: string | null;
  error_message: string | null;
  updated_at: number;
}

export interface CreateSessionResponse {
  session_id: string;
  snapshot: SessionSnapshot;
}

export interface StartSessionRequest {
  query: string;
}

export interface SendMessageRequest {
  text: string;
}
