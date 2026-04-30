"""
InduSafe Sentinel - Evidence Capture
"""
import cv2
import os
import time
from datetime import datetime
from typing import Optional, List
import threading


class EvidenceCapture:
    def __init__(self, upload_folder: str, video_duration: int = 5):
        self.upload_folder = upload_folder
        self.video_duration = video_duration
        self.frame_buffer = []
        self.buffer_lock = threading.Lock()
        self.max_buffer_size = 30 * video_duration  # 30 fps * duration
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
    
    def update_buffer(self, frame):
        """Update the frame buffer for video recording"""
        with self.buffer_lock:
            self.frame_buffer.append(frame.copy())
            # Keep only recent frames
            if len(self.frame_buffer) > self.max_buffer_size:
                self.frame_buffer.pop(0)
    
    def capture_violation(self, frame, worker_name: str, 
                         violation_type: str, capture_video: bool = False) -> dict:
        """
        Capture violation evidence (image and optional video)
        
        Args:
            frame: Frame to capture
            worker_name: Name of worker
            violation_type: Type of violation
            capture_video: Whether to capture video (default False)
        
        Returns:
            dict with paths to saved files
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Create filename base
        safe_worker_name = worker_name.replace(' ', '_') if worker_name else 'Unknown'
        base_filename = f"{safe_worker_name}_{violation_type}_{timestamp_str}"
        
        # Save image
        image_filename = f"{base_filename}.jpg"
        image_path = os.path.join(self.upload_folder, image_filename)
        cv2.imwrite(image_path, frame)
        
        video_filename = None
        video_path = None
        
        # Save video only if enabled
        if capture_video and self.video_duration > 0:
            video_filename = f"{base_filename}.mp4"
            video_path = os.path.join(self.upload_folder, video_filename)
            self._save_video(video_path)
        
        print(f"Evidence captured: {image_filename}" + (f", {video_filename}" if video_filename else ""))
        
        return {
            'image_path': image_path,
            'video_path': video_path,
            'image_filename': image_filename,
            'video_filename': video_filename,
            'timestamp': timestamp.isoformat()
        }
    
    def _save_video(self, video_path: str):
        """Save video from frame buffer"""
        with self.buffer_lock:
            if len(self.frame_buffer) == 0:
                return
            
            # Get frame dimensions
            height, width = self.frame_buffer[0].shape[:2]
            
            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 30.0
            out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
            
            # Write frames
            for frame in self.frame_buffer:
                out.write(frame)
            
            out.release()
    
    def draw_timestamp(self, frame, worker_name: str = None, 
                      violation_type: str = None):
        """Draw timestamp and info on frame"""
        output = frame.copy()
        
        # Draw timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(output, timestamp, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw worker info
        if worker_name:
            text = f"Worker: {worker_name}"
            cv2.putText(output, text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw violation info
        if violation_type:
            text = f"Violation: {violation_type.replace('_', ' ').title()}"
            cv2.putText(output, text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return output
    
    def cleanup_old_files(self, max_age_days: int = 30):
        """Remove evidence files older than specified days"""
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        for filename in os.listdir(self.upload_folder):
            file_path = os.path.join(self.upload_folder, filename)
            
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    print(f"Removed old evidence: {filename}")
