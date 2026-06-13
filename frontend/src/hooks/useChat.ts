import { useCallback, useRef, useState } from "react";
import type { Message, WsEvent, AgentThought, ToolCallLog } from "../types";

interface StreamingMessage {
  thinking: string[];
  toolCalls: { tool: string; step: number }[];
}

export function useChat(threadId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState<StreamingMessage | null>(null);
  const [sending, setSending] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const setInitialMessages = useCallback((msgs: Message[]) => {
    setMessages(msgs);
  }, []);

  const handleWsEvent = useCallback((event: WsEvent) => {
    switch (event.type) {
      case "agent_thinking":
        setStreaming((prev) => ({
          thinking: [...(prev?.thinking ?? []), event.content ?? ""],
          toolCalls: prev?.toolCalls ?? [],
        }));
        break;

      case "tool_call":
        setStreaming((prev) => ({
          thinking: prev?.thinking ?? [],
          toolCalls: [
            ...(prev?.toolCalls ?? []),
            { tool: event.tool ?? "", step: event.step ?? 0 },
          ],
        }));
        break;

      case "agent_response": {
        const assistantMsg: Message = {
          id: `streaming-${Date.now()}`,
          thread_id: threadId ?? "",
          role: "assistant",
          content: event.content ?? "",
          agent_thoughts: (event.thoughts ?? []) as AgentThought[],
          tool_calls: (event.tool_calls ?? []) as ToolCallLog[],
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setStreaming(null);
        break;
      }

      case "message_saved":
        // Update the last assistant message id with the persisted one
        if (event.message_id) {
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1 && m.role === "assistant"
                ? { ...m, id: event.message_id! }
                : m
            )
          );
        }
        setSending(false);
        break;

      case "done":
        setSending(false);
        setStreaming(null);
        break;

      case "error":
        setSending(false);
        setStreaming(null);
        break;
    }
  }, [threadId]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || !wsRef.current || sending) return;

      const userMsg: Message = {
        id: `local-${Date.now()}`,
        thread_id: threadId ?? "",
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setSending(true);
      setStreaming({ thinking: [], toolCalls: [] });

      wsRef.current.send(JSON.stringify({ type: "message", content }));
    },
    [threadId, sending]
  );

  return {
    messages,
    streaming,
    sending,
    wsRef,
    setInitialMessages,
    handleWsEvent,
    sendMessage,
  };
}
