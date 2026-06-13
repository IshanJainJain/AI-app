"""
Base Agent — ReAct loop (THINK → ACT → OBSERVE).

All specialist agents inherit this class.
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.mcp.base import adapter_registry
from app.telemetry.otel import trace_span, record_agent_task, record_llm_latency, get_current_trace_id

logger = logging.getLogger(__name__)

MAX_STEPS = 12


class BaseAgent(ABC):
    agent_type: str = "base"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self):
        self.llm = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        self.logger = logging.getLogger(f"agent.{self.agent_type}")

    @abstractmethod
    def get_available_tools(self) -> list[str]:
        ...

    @abstractmethod
    async def build_task_prompt(self, context: dict) -> str:
        ...

    async def run(self, context: dict) -> dict:
        """
        Execute the ReAct loop.

        context keys:
          - thread_id, user_id, prompt, messages (history),
            global_context, image_contexts

        Returns a result dict with:
          - response, thoughts, tool_calls, status, error
        """
        trace_id = get_current_trace_id()
        started_at = datetime.now(timezone.utc).isoformat()

        with trace_span(f"agent.{self.agent_type}.run", {"thread_id": context.get("thread_id", "")}):
            try:
                result = await self._react_loop(context)
                result["status"] = "completed"
            except Exception as exc:
                self.logger.error("Agent run failed: %s", exc)
                result = {"response": f"I encountered an error: {exc}", "thoughts": [], "tool_calls": [], "status": "failed", "error": str(exc)}

        result["trace_id"] = trace_id
        result["started_at"] = started_at
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        record_agent_task(self.agent_type, result["status"])
        return result

    async def _react_loop(self, context: dict) -> dict:
        tools = self._get_tool_definitions()
        tool_map = adapter_registry.get_tool_map()

        user_prompt = await self.build_task_prompt(context)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        thoughts: list[dict] = []
        tool_calls_log: list[dict] = []

        for step in range(1, MAX_STEPS + 1):
            llm_start = time.monotonic()
            response = await self._call_llm(messages, tools)
            llm_ms = int((time.monotonic() - llm_start) * 1000)
            record_llm_latency(llm_ms, settings.LLM_MODEL, self.agent_type)

            choice = response.choices[0]
            message = choice.message

            thought_entry = {
                "step": step,
                "thought": message.content or "(no thought)",
                "action": None,
                "observation": None,
            }
            thoughts.append(thought_entry)

            if choice.finish_reason == "stop" or not message.tool_calls:
                return {
                    "response": message.content or "",
                    "thoughts": thoughts,
                    "tool_calls": tool_calls_log,
                }

            messages.append(message.model_dump(exclude_none=True))

            for tc in message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_params = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_params = {}

                thought_entry["action"] = fn_name
                thought_entry["action_input"] = fn_params

                adapter = tool_map.get(fn_name)
                if not adapter:
                    observation = f"Tool '{fn_name}' not found in registry."
                else:
                    result = await adapter.safe_execute(fn_name, fn_params)
                    observation = json.dumps(result.get("data", result))
                    tool_calls_log.append({
                        "step": step,
                        "tool": fn_name,
                        "params": fn_params,
                        "result": result.get("data"),
                        "success": result.get("success"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                thought_entry["observation"] = observation[:500]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": observation,
                })

        return {
            "response": "I reached the maximum number of reasoning steps without a final answer.",
            "thoughts": thoughts,
            "tool_calls": tool_calls_log,
        }

    async def _call_llm(self, messages: list[dict], tools: list[dict]):
        return await self.llm.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        available = set(self.get_available_tools())
        return [t for t in adapter_registry.all_tools() if t["function"]["name"] in available]
