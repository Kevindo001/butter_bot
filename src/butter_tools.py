"""Central tool dispatcher for Butter.

Imports the tool functions from each category module (butter_camera,
butter_motors, butter_calendar, butter_memory, butter_search), parses
<action> tags emitted by the Brain (see prompts/system_prompt.txt), and
routes each parsed call to the matching function.
"""

from src.butter_camera import (
    capture_image,
    find_person,
    find_object,
    get_world_state,
    stream_start,
)
from src.butter_motors import (
    move_forward,
    move_backward,
    rotate_left,
    rotate_right,
    stop,
)
from src.butter_calendar import get_calendar_events, create_calendar_event
from src.butter_memory import read_memory, save_memory
from src.butter_search import search_query

TOOL_REGISTRY = {
    "capture_image": capture_image,
    "find_person": find_person,
    "find_object": find_object,
    "get_world_state": get_world_state,
    "stream_start": stream_start,
    "move_forward": move_forward,
    "move_backward": move_backward,
    "rotate_left": rotate_left,
    "rotate_right": rotate_right,
    "stop": stop,
    "get_calendar_events": get_calendar_events,
    "create_calendar_event": create_calendar_event,
    "read_memory": read_memory,
    "save_memory": save_memory,
    "search_query": search_query,
}


def parse_action(action_text):
    """Parse a single <action>...</action> block into a tool name and args.

    Input: action_text (string — the raw contents of one <action> tag)
    Output: TBD — (tool_name, args) or equivalent parsed call
    """
    raise NotImplementedError


def dispatch(action_text):
    """Parse an <action> block and call the matching tool from TOOL_REGISTRY.

    Input: action_text (string — the raw contents of one <action> tag)
    Output: TBD — result of the dispatched tool call
    """
    raise NotImplementedError
