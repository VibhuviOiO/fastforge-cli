"""Agent orchestrator — tool-calling agent loop skeleton.

This is the infrastructure skeleton. You add your business logic:
- Tool definitions and implementations
- System prompts for the agent persona
- Memory/state management between turns
- Guardrails and safety checks
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import structlog
from opentelemetry import trace

from app.ai.gateway import CompletionRequest, GatewayClient

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class Tool:
    """A tool the agent can invoke."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema for tool parameters
    handler: Callable[..., Awaitable[str]]  # async function that executes the tool


@dataclass
class AgentMessage:
    """A message in the agent conversation."""

    role: str  # system | user | assistant | tool
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentQuery:
    """Input for the agent."""

    message: str
    conversation_history: list[AgentMessage] = field(default_factory=list)
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_iterations: int = 10
    system_prompt: str | None = None


@dataclass
class AgentResponse:
    """Agent response after completing its reasoning loop."""

    answer: str
    tool_calls_made: list[dict[str, Any]]
    iterations: int
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """Tool-calling agent loop orchestrator.

    Loop:
    1. Send messages to LLM
    2. If LLM returns tool calls → execute tools → append results → goto 1
    3. If LLM returns a final answer → return

    Override methods to add:
    - Custom tools (register via add_tool)
    - Guardrails before/after tool execution
    - Memory persistence between conversations
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful AI assistant with access to tools. "
        "Use the tools when needed to answer the user's question. "
        "Think step by step and explain your reasoning."
    )

    def __init__(self, gateway: GatewayClient, max_iterations: int = 10) -> None:
        self._gateway = gateway
        self._max_iterations = max_iterations
        self._tools: dict[str, Tool] = {}

    def add_tool(self, tool: Tool) -> None:
        """Register a tool the agent can use."""
        self._tools[tool.name] = tool

    @tracer.start_as_current_span("agent.orchestrate")
    async def run(self, query: AgentQuery) -> AgentResponse:
        """Execute the agent loop."""
        messages: list[dict[str, str]] = []
        tool_calls_made: list[dict[str, Any]] = []
        max_iter = query.max_iterations or self._max_iterations

        # System prompt
        system_prompt = query.system_prompt or self.DEFAULT_SYSTEM_PROMPT
        messages.append({"role": "system", "content": system_prompt})

        # Conversation history
        for msg in query.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        # User message
        messages.append({"role": "user", "content": query.message})

        # Agent loop
        for iteration in range(max_iter):
            with trace.get_tracer(__name__).start_as_current_span(
                f"agent.iteration.{iteration}"
            ):
                tool_schemas = self._get_tool_schemas()
                request = CompletionRequest(
                    model=query.model,
                    messages=messages,
                    temperature=query.temperature,
                    max_tokens=4096,
                    tools=tool_schemas or None,
                    tool_choice="auto" if tool_schemas else None,
                )

                response = await self._gateway.complete(request)

                # Check if the response contains tool calls
                if response.metadata.get("tool_calls"):
                    # Execute each tool call
                    for tool_call in response.metadata["tool_calls"]:
                        tool_result = await self._execute_tool(tool_call)
                        tool_calls_made.append(tool_call)

                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [tool_call],
                        })
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "tool_call_id": tool_call.get("id", ""),
                        })
                else:
                    # Final answer
                    return AgentResponse(
                        answer=response.content,
                        tool_calls_made=tool_calls_made,
                        iterations=iteration + 1,
                        model=query.model,
                    )

        # Max iterations reached
        return AgentResponse(
            answer="I was unable to complete the task within the allowed iterations.",
            tool_calls_made=tool_calls_made,
            iterations=max_iter,
            model=query.model,
            metadata={"reason": "max_iterations_reached"},
        )

    @tracer.start_as_current_span("agent.execute_tool")
    async def _execute_tool(self, tool_call: dict[str, Any]) -> str:
        """Execute a tool and return its result as a string."""
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        raw_args = function.get("arguments", {})

        # OpenAI returns arguments as a JSON-encoded string; LiteLLM may already decode.
        if isinstance(raw_args, str):
            try:
                arguments = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError as e:
                logger.error("agent.tool.bad_arguments", tool=tool_name, error=str(e))
                return f"Error: invalid JSON arguments for {tool_name}: {e}"
        else:
            arguments = raw_args or {}

        if tool_name not in self._tools:
            return f"Error: Tool '{tool_name}' not found."

        tool = self._tools[tool_name]
        try:
            result = await tool.handler(**arguments)
            logger.info("agent.tool.success", tool=tool_name)
            return result
        except Exception as e:
            logger.error("agent.tool.error", tool=tool_name, error=str(e))
            return f"Error executing {tool_name}: {e}"

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tool schemas."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]
