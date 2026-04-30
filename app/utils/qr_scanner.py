"""
InduSafe Sentinel - QR Code Scanner
Fast and reliable QR code detection using OpenCV
"""
import cv2
import numpy as np
from typing import List, Dict, Optional


class QRScanner:
    def __init__(self):
        self.detector = cv2.QRCodeDetector()
        self.last_scan_time = 0
        self.scan_results = {}  # Cache results to avoid re-reading same QR
        
    def scan_frame(self, frame) -> List[Dict]:
        """
        Scan frame for QR codes - returns list of detected QR codes
        Optimized for speed and reliability
        """
        detections = []
        
        try:
            # Try to detect multiple QR codes
            ret, decoded_info, points, _ = self.detector.detectAndDecodeMulti(frame)
            
            if ret and decoded_info:
                for i, data in enumerate(decoded_info):
                    if data:
                        # Get bounding box points
                        bbox = points[i]
                        
                        # Calculate rect
                        x_coords = [int(p[0]) for p in bbox]
                        y_coords = [int(p[1]) for p in bbox]
                        x, y = min(x_coords), min(y_coords)
                        w, h = max(x_coords) - x, max(y_coords) - y
                        
                        detection = {
                            'data': data,
                            'rect': {
                                'x': x,
                                'y': y,
                                'width': w,
                                'height': h
                            },
                            'polygon': [(int(p[0]), int(p[1])) for p in bbox],
                            'type': 'QRCODE'
                        }
                        detections.append(detection)
                        
        except Exception as e:
            # Fallback to single QR detection
            try:
                data, bbox, _ = self.detector.detectAndDecode(frame)
                if data and bbox is not None:
                    bbox = bbox[0]
                    x_coords = [int(p[0]) for p in bbox]
                    y_coords = [int(p[1]) for p in bbox]
                    x, y = min(x_coords), min(y_coords)
                    w, h = max(x_coords) - x, max(y_coords) - y
                    
                    detection = {
                        'data': data,
                        'rect': {
                            'x': x,
                            'y': y,
                            'width': w,
                            'height': h
                        },
                        'polygon': [(int(p[0]), int(p[1])) for p in bbox],
                        'type': 'QRCODE'
                    }
                    detections.append(detection)
            except Exception as e2:
                pass
        
        return detections
    
    def draw_detections(self, frame, detections: List[Dict]):
        """Draw QR code bounding boxes on frame"""
        output = frame.copy()
        
        for detection in detections:
            # Draw polygon
            points = np.array(detection['polygon'], np.int32)
            points = points.reshape((-1, 1, 2))
            cv2.polylines(output, [points], True, (0, 255, 0), 2)
            
            # Draw text with background
            x, y = detection['rect']['x'], detection['rect']['y']
            text = str(detection['data'])[:25]
            
            # Text background
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(output, (x, y - text_h - 10), (x + text_w, y), (0, 255, 0), -1)
            cv2.putText(output, text, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return output
    
    def extract_worker_id(self, qr_data: str) -> Optional[str]:
        """
        Extract worker ID from QR code data
        Expected formats: "WORKER:EMP001" or "EMP001" or "NAME:John" or just "John"
        """
        if not qr_data:
            return None
        
        qr_data = qr_data.strip()
        
        # Handle WORKER: prefix
        if qr_data.upper().startswith('WORKER:'):
            return qr_data.split(':', 1)[1].strip()
        
        # Handle NAME: prefix
        if qr_data.upper().startswith('NAME:'):
            return qr_data.split(':', 1)[1].strip()
        
        # Return as-is (assume it's the employee ID or name)
        return qr_data
