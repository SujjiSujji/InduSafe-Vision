"""
InduSafe Sentinel - PPE Detector using YOLOv8
"""
import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Optional
import os


class PPEDetector:
    def __init__(self, model_path: str = None, confidence: float = 0.5):
        self.confidence = confidence
        
        # Load model
        if model_path and os.path.exists(model_path):
            self.model = YOLO(model_path)
        else:
            # Use pre-trained COCO model
            self.model = YOLO('yolov8n.pt')
        
        print(f"PPE Detector initialized with confidence: {confidence}")
    
    def detect(self, frame) -> Dict:
        """
        Detect PPE in frame
        Returns detection results with bounding boxes and labels
        """
        results = self.model(frame, verbose=False)
        
        detections = {
            'persons': [],
            'hard_hats': [],
            'violations': []
        }
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Get box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()
                class_id = int(box.cls[0].cpu().numpy())
                class_name = result.names[class_id]
                
                if confidence < self.confidence:
                    continue
                
                detection = {
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': float(confidence),
                    'class': class_name,
                    'class_id': class_id
                }
                
                # Categorize detections
                if class_name == 'person':
                    detections['persons'].append(detection)
        
        # For hard hat detection, we'll check if there's something on the head
        # Since YOLOv8n doesn't have hard hat class, we use a simple heuristic
        # In a real system, you'd train a custom model
        detections['violations'] = self._check_violations(detections)
        
        return detections
    
    def _check_violations(self, detections: Dict) -> List[Dict]:
        """
        Check for PPE violations
        For demo: assume violation if person detected (simplified)
        In production: use custom trained model for hard hats
        """
        violations = []
        
        for person in detections['persons']:
            # For demo purposes, we'll flag every person as violation
            # In real system, you'd check for hard hat presence
            violation = {
                'type': 'hard_hat_missing',
                'person_bbox': person['bbox'],
                'confidence': person['confidence']
            }
            violations.append(violation)
        
        return violations
    
    def draw_detections(self, frame, detections: Dict):
        """Draw detection bounding boxes on frame"""
        output = frame.copy()
        
        # Draw persons (blue)
        for person in detections['persons']:
            x1, y1, x2, y2 = person['bbox']
            cv2.rectangle(output, (x1, y1), (x2, y2), (255, 0, 0), 2)
            label = f"Person: {person['confidence']:.2f}"
            cv2.putText(output, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # Draw violations (red)
        for violation in detections['violations']:
            x1, y1, x2, y2 = violation['person_bbox']
            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label = "VIOLATION: Hard Hat Missing!"
            cv2.putText(output, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        return output
