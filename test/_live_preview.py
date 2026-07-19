"""Shared MJPEG preview server for manual camera test scripts (not part of
the runtime pipeline). Serves whatever frame was last handed to it via
set_display_frame(), defaulting to the raw camera feed.
"""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class LivePreview:
    def __init__(self, camera_index=0, port=8080, frame_source=None):
        """frame_source: optional zero-arg callable returning a frame (or
        None). If given, LivePreview polls it instead of opening its own
        cv2.VideoCapture - use this when another part of the process
        already owns the camera (e.g. butter_camera's stream_start()),
        since most USB cameras reject a second concurrent capture handle."""
        self.camera_index = camera_index
        self.port = port
        self.frame_source = frame_source
        self._cap = None
        self._server = None
        self._lock = threading.Lock()
        self._latest_frame = None
        self._display_frame = None
        self._stop = threading.Event()

    def start(self):
        if self.frame_source is None:
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                raise RuntimeError(f"failed to open camera index {self.camera_index}")

        threading.Thread(target=self._capture_loop, daemon=True).start()

        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        print(f"Live preview: http://<jetson-ip>:{self.port}")
        print(f"  (SSHed in? run `ssh -L {self.port}:localhost:{self.port} ...` and open http://localhost:{self.port})")

    def stop(self):
        self._stop.set()
        if self._server is not None:
            self._server.shutdown()
        if self._cap is not None:
            self._cap.release()

    def get_frame(self):
        """Latest raw frame straight off the camera."""
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def set_display_frame(self, frame):
        """Override what gets streamed (e.g. a frame with detection boxes drawn on it)."""
        with self._lock:
            self._display_frame = frame

    def _capture_loop(self):
        while not self._stop.is_set():
            if self.frame_source is not None:
                frame = self.frame_source()
                ok = frame is not None
            else:
                ok, frame = self._cap.read()
            if ok:
                with self._lock:
                    self._latest_frame = frame
                    if self._display_frame is None:
                        self._display_frame = frame
            time.sleep(1 / 30)

    def _get_display_frame(self):
        with self._lock:
            return None if self._display_frame is None else self._display_frame.copy()

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # silence per-request logging, keeps test-script prompts readable

            def do_GET(self):
                if self.path == "/":
                    body = b'<html><body style="margin:0"><img src="/stream"></body></html>'
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if self.path != "/stream":
                    self.send_response(404)
                    self.end_headers()
                    return

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while not outer._stop.is_set():
                        frame = outer._get_display_frame()
                        if frame is None:
                            time.sleep(0.05)
                            continue
                        ok, buf = cv2.imencode(".jpg", frame)
                        if not ok:
                            continue
                        jpeg_bytes = buf.tobytes()
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode())
                        self.wfile.write(jpeg_bytes)
                        self.wfile.write(b"\r\n")
                        time.sleep(1 / 15)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # client (browser tab) closed the stream

        return Handler
