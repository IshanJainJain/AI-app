"""
Chat Agent — conversational specialist with KB search tools.

Decides whether to search the knowledge base before answering.
Streams each ReAct step back to the caller via an async generator.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.agents.base_agent import BaseAgent, MAX_STEPS
from app.guardrails.guardrails import guardrails
from app.memory.memory import episodic_memory
from app.mcp.base import adapter_registry
from app.telemetry.otel import record_llm_latency

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    agent_type = "chat_agent"
    system_prompt = (
        "You are a helpful AI assistant with access to a local knowledge base.\n"
        "When the user's question may be answered by stored documents, "
        "use the search_knowledge_base tool first.\n"
        "Cite the source document when your answer comes from the knowledge base.\n"
        "Be concise, accurate, and honest. If you don't find relevant information, say so.\n"
        "Never make up facts — prefer 'I don't know' over guessing."
    )

    def get_available_tools(self) -> list[str]:
        return ["search_knowledge_base", "get_document_info"]

    async def build_task_prompt(self, context: dict) -> str:
        parts = []

        if context.get("global_context", "").strip():
            parts.append(f"Global instructions:\n{context['global_context'].strip()}")

        if context.get("image_contexts"):
            imgs = "\n\n".join(
                f"Image '{i['filename']}':\n{i['description']}"
                for i in context["image_contexts"]
            )
            parts.append(f"Image context for this conversation:\n{imgs}")

        memories = await episodic_memory.recall(context.get("user_id", ""), limit=3)
        if memories:
            parts.append(episodic_memory.build_context_block(memories))

        history = context.get("messages", [])
        if history:
            history_lines = []
            for m in history[-20:]:  # last 20 messages
                speaker = "User" if m["role"] == "user" else "Assistant"
                history_lines.append(f"{speaker}: {m['content']}")
            parts.append("Conversation history:\n" + "\n\n".join(history_lines))

        parts.append(f"User: {context['prompt']}")
        return "\n\n".join(parts)

    async def stream(self, context: dict) -> AsyncGenerator[dict, None]:
        """
        Run the ReAct loop and yield structured events:
          agent_thinking, tool_call, tool_result, agent_response, done, error
        """
        user_id = context.get("user_id", "")

        # Guardrail check
        guard = guardrails.check_message(user_id, context.get("prompt", ""))
        if not guard["allowed"]:
            yield {"type": "error", "content": guard["reason"]}
            return

        tools = self._get_tool_definitions()
        tool_map = adapter_registry.get_tool_map()

        user_prompt = await self.build_task_prompt(context)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        thoughts: list[dict] = []
        tool_calls_log: list[dict] = []
        kb_sources: list[str] = []

        for step in range(1, MAX_STEPS + 1):
            llm_start = time.monotonic()
            try:
                response = await self._call_llm(messages, tools)
            except Exception as exc:
                yield {"type": "error", "content": f"LLM error: {exc}"}
                return

            llm_ms = int((time.monotonic() - llm_start) * 1000)
            record_llm_latency(llm_ms, settings.LLM_MODEL, self.agent_type)

            choice = response.choices[0]
            message = choice.message

            if message.content:
                yield {"type": "agent_thinking", "step": step, "content": message.content}

            thought = {"step": step, "thought": message.content or ""}
            thoughts.append(thought)

            if choice.finish_reason == "stop" or not message.tool_calls:
                final = message.content or ""
                guard_resp = guardrails.check_response(final, user_id)
                if not guard_resp["allowed"]:
                    yield {"type": "error", "content": guard_resp["reason"]}
                    return

                yield {"type": "agent_response", "content": final, "thoughts": thoughts, "tool_calls": tool_calls_log}

                # Store in episodic memory (fire-and-forget)
                try:
                    await episodic_memory.store(
                        thread_id=context.get("thread_id", ""),
                        user_id=user_id,
                        query=context.get("prompt", ""),
                        response_summary=final[:300],
                        tools_used=[tc["tool"] for tc in tool_calls_log],
                        kb_sources=kb_sources,
                    )
                except Exception:
                    pass

                yield {"type": "done"}
                return

            messages.append(message.model_dump(exclude_none=True))

            for tc in message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_params = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_params = {}

                thought["action"] = fn_name
                thought["action_input"] = fn_params

                guard_tool = guardrails.check_tool_call(fn_name, fn_params, user_id)
                if not guard_tool["allowed"]:
                    yield {"type": "error", "content": f"Tool call blocked: {guard_tool['reason']}"}
                    return

                yield {"type": "tool_call", "step": step, "tool": fn_name, "params": fn_params}

                adapter = tool_map.get(fn_name)
                if not adapter:
                    observation = f"Tool '{fn_name}' not found."
                    result_data = None
                else:
                    result = await adapter.safe_execute(fn_name, fn_params)
                    observation = json.dumps(result.get("data", result))
                    result_data = result.get("data")

                    # Track KB sources used
                    if fn_name == "search_knowledge_base" and result_data:
                        kb_sources.extend(
                            c.get("source", "") for c in result_data.get("chunks", [])
                        )

                    tool_calls_log.append({
                        "step": step,
                        "tool": fn_name,
                        "params": fn_params,
                        "result": result_data,
                        "success": result.get("success"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                thought["observation"] = observation[:500]
                yield {"type": "tool_result", "step": step, "tool": fn_name, "data": result_data}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": observation,
                })

        yield {
            "type": "agent_response",
            "content": "I reached the maximum reasoning steps without a final answer.",
            "thoughts": thoughts,
            "tool_calls": tool_calls_log,
        }
        yield {"type": "done"}
