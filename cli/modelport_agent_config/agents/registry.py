from __future__ import annotations

from modelport_agent_config.agents.base import AgentAdapter
from modelport_agent_config.agents.claude_code import ClaudeCodeAdapter

_AGENTS: dict[str, AgentAdapter] = {
    ClaudeCodeAdapter.id: ClaudeCodeAdapter(),
}


def list_agents() -> list[AgentAdapter]:
    return list(_AGENTS.values())


def get_agent(agent_id: str) -> AgentAdapter:
    normalized = agent_id.strip().lower()
    adapter = _AGENTS.get(normalized)
    if adapter is None:
        known = ", ".join(sorted(_AGENTS))
        raise KeyError(f"Unknown agent {agent_id!r}. Available: {known}")
    return adapter
