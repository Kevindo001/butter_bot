"""Memory tools for Butter.

Covers reading and writing the persistent memory context that gets
injected into prompts/system_prompt.txt's {{MEMORY_CONTEXT}} slot each
turn — facts and past interactions the Brain should have available
without re-deriving them from scratch.
"""


def read_memory():
    """Retrieve stored memory context relevant to the current turn.

    Input: TBD — likely a query or the current transcript for relevance matching
    Output: TBD — memory context to inject into the system prompt
    """
    raise NotImplementedError


def save_memory(content):
    """Persist a new fact or interaction to memory.

    Input: content (string)
    Output: none
    """
    raise NotImplementedError
