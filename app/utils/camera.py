"""
InduSafe Sentinel - Camera Handler
"""
import cv2
import threading
import time
from typing import Optional, Callable


class Camera:
    def __init__(self, camera_index: int = 0, width: int = 640, 
                 height: int = 480, fps: int = 30):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None
        self.is_running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.capture_thread = None
        
    def start(self) -> bool:
        """Start the camera capture"""
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}")
            return False
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        print(f"Camera started: {self.width}x{self.height} @ {self.fps}fps")
        return True
    
    def _capture_loop(self):
        """Continuously capture frames in a separate thread"""
        while self.is_running:
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame.copy()
            time.sleep(0.001)  # Small delay to prevent CPU overload
    
    def get_frame(self) -> Optional:
        """Get the current frame"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def stop(self):
        """Stop the camera capture"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        print("Camera stopped")
    
    def is_active(self) -> bool:
        """Check if camera is active"""
        return self.is_running and self.cap is not None and self.cap.isOpened()
