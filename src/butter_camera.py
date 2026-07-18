"""Camera and vision tools for Butter.

Covers everything that reads from the USB camera or the vision pipeline
(OpenCV / Jetson Inference + TensorRT): capturing frames, detecting people
or objects in view, summarizing world state for the Brain, and starting a
live video stream. See docs/tools.md and docs/architecture.md (layer 5)
for the contract each of these is expected to fulfill once implemented.
"""


def capture_image():
    """Grab a single frame from the USB camera.

    Input: none
    Output: image frame (format TBD once the vision pipeline is implemented)
    """
    raise NotImplementedError


def find_person():
    """Locate a person in the current camera view.

    Input: none
    Output: TBD — structured detection result (e.g. bounding box, confidence)
    """
    raise NotImplementedError


def find_object(label):
    """Locate a named object in the current camera view.

    Input: label (string — what to look for)
    Output: TBD — structured detection result (e.g. bounding box, confidence)
    """
    raise NotImplementedError


def get_world_state():
    """Summarize what the vision pipeline currently sees for the Brain.

    Input: none
    Output: TBD — structured summary of detected people/objects
    """
    raise NotImplementedError


def stream_start():
    """Start a live video stream from the USB camera.

    Input: none
    Output: TBD — stream handle or endpoint
    """
    raise NotImplementedError
