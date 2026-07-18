"""Calendar tools for Butter.

Covers reading and writing calendar events on behalf of the user. Not yet
wired to a calendar provider — see docs/tools.md for tool status; until
this is implemented, prompts/system_prompt.txt should not claim calendar
access is available.
"""


def get_calendar_events():
    """Retrieve upcoming events from the user's calendar.

    Input: TBD — likely a date/time range
    Output: TBD — list of calendar events
    """
    raise NotImplementedError


def create_calendar_event(title, start_time):
    """Create a new event on the user's calendar.

    Input: title (string), start_time (TBD format)
    Output: TBD — created event confirmation
    """
    raise NotImplementedError
