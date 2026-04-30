"""
InduSafe Sentinel - Main Application Entry Point

This module initializes and runs the complete InduSafe Sentinel system:
- Camera capture
- PPE detection
- QR code identification
- Voice alerts
- Evidence capture
- Flask web dashboard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import time
import signal
from datetime import datetime
from flask import Flask
import cv2  # Import cv2 here for use in the class

from app import create_app
from app.models import Database, Worker, Violation, Alert
from app.utils import Camera, PPEDetector, QRScanner, VoiceAlert, EvidenceCapture
from app.utils.reports import EmailReporter
from app.routes import main_bp, detection_system as routes_detection_system
from config import Config


class DetectionSystem:
    """
    Main detection system that integrates all components
    """
    
    def __init__(self, config_class=Config):
        self.config = config_class
        self.is_running = False
        self.detection_thread = None
        
        # Initialize components
        print("Initializing InduSafe Sentinel...")
        
        # Camera
        self.camera = Camera(
            camera_index=self.config.CAMERA_INDEX,
            width=self.config.CAMERA_WIDTH,
            height=self.config.CAMERA_HEIGHT,
            fps=self.config.CAMERA_FPS
        )
        
        # PPE Detector
        self.detector = PPEDetector(
            confidence=self.config.DETECTION_CONFIDENCE
        )
        
        # QR Scanner
        self.qr_scanner = QRScanner()
        
        # Voice Alert
        self.voice_alert = VoiceAlert(
            volume=self.config.VOICE_ALERT_VOLUME,
            rate=self.config.VOICE_ALERT_RATE,
            enabled=self.config.VOICE_ALERT_ENABLED
        )
        
        # Evidence Capture
        self.evidence = EvidenceCapture(
            upload_folder=self.config.UPLOAD_FOLDER,
            video_duration=self.config.EVIDENCE_VIDEO_DURATION
        )
        
        # Database
        self.db = Database(self.config.DATABASE_PATH)
        self.db.init_db()
        
        # Models
        self.worker_model = Worker(self.db)
        self.violation_model = Violation(self.db)
        self.alert_model = Alert(self.db)
        
        # State
        self.current_display_frame = None
        self.recent_violations = {}  # Track recent violations for cooldown
        self.violation_counters = {}  # Track consecutive violations per worker
        self.violation_frame_counts = {}  # Track frame counts for violation persistence
        self.image_capture_counters = {}  # Track image captures per worker
        self.last_frame_with_violation = {}  # Track when we last saw violation per worker
        self.camera_enabled = True  # Camera toggle state
        self.session_start = datetime.now()  # Track session start time
        
        # Email Reporter (uses config for permanent settings)
        self.email_reporter = EmailReporter(config=self.config)
        
        print("InduSafe Sentinel initialized successfully!")
    
    def start(self):
        """Start the detection system"""
        print("Starting detection system...")
        
        # Start camera
        if not self.camera.start():
            print("ERROR: Failed to start camera!")
            return False
        
        # Voice alert system is ready (initialized in constructor)
        
        # Start detection loop in separate thread
        self.is_running = True
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        print("Detection system started!")
        return True
    
    def stop(self):
        """Stop the detection system and send email report"""
        print("Stopping detection system...")
        self.is_running = False
        
        if self.detection_thread:
            self.detection_thread.join(timeout=2.0)
        
        self.camera.stop()
        
        # Send email report
        print("\n[EMAIL] Preparing session report...")
        self._send_session_report()
        
        print("Detection system stopped!")
    
    def _send_session_report(self):
        """Send session summary email and individual worker reports"""
        try:
            # Get all violations and workers for the session
            violations = self.violation_model.get_all(limit=1000)
            workers = self.worker_model.get_all()
            
            print(f"\n[EMAIL] Preparing reports for {len(workers)} workers...")
            print(f"[EMAIL] Total violations in session: {len(violations)}")
            
            # 1. Send supervisor report
            supervisor_email = self.email_reporter.supervisor_email
            if supervisor_email and supervisor_email != "supervisor@company.com":
                print(f"[EMAIL] Sending supervisor report to: {supervisor_email}")
                self.email_reporter.send_session_report(
                    supervisor_email,
                    self.session_start,
                    violations,
                    workers
                )
            else:
                print("[EMAIL] No SUPERVISOR_EMAIL configured. Skipping supervisor report.")
            
            # 2. Send individual worker reports
            print("\n[EMAIL] Sending individual worker reports...")
            results = self.email_reporter.send_worker_reports(workers, violations)
            
            print(f"[EMAIL] Worker reports: {results['sent']} sent, {results['failed']} failed, {results['skipped']} skipped")
            
            # Print details
            for detail in results['details']:
                if detail['status'] == 'sent':
                    print(f"  ✓ {detail['worker']} → {detail['email']}")
                elif detail['status'] == 'failed':
                    print(f"  ✗ {detail['worker']} → {detail.get('email', 'N/A')}")
                
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send reports: {e}")
    
    def _detection_loop(self):
        """Main detection loop"""
        frame_count = 0
        
        while self.is_running:
            try:
                # Check if camera is enabled
                if not self.camera_enabled:
                    # Create a blank frame with message
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Camera Paused", (200, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv2.putText(frame, "Click 'Resume Camera' to continue", (150, 280),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                    self.current_display_frame = frame
                    time.sleep(0.1)
                    continue
                
                # Get frame from camera
                frame = self.camera.get_frame()
                
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                # Update evidence buffer
                self.evidence.update_buffer(frame)
                
                # Detect PPE
                detections = self.detector.detect(frame)
                
                # Scan for QR codes
                qr_detections = self.qr_scanner.scan_frame(frame)
                
                # Identify workers from QR codes
                identified_workers = []
                for qr in qr_detections:
                    qr_data = qr['data']
                    worker_id = self.qr_scanner.extract_worker_id(qr_data)
                    if worker_id:
                        # Try to find worker by QR code (employee_id)
                        worker = self.worker_model.get_by_qr(worker_id)
                        if worker:
                            identified_workers.append({
                                'worker': worker,
                                'qr_bbox': qr['rect'],
                                'qr_data': qr_data
                            })
                            print(f"[QR] Identified worker: {worker['name']} (ID: {worker_id})")
                        else:
                            print(f"[QR] No worker found for ID: {worker_id}")
                
                # Check for violations and alert
                if detections['violations']:
                    self._handle_violations(
                        frame, detections, identified_workers, frame_count
                    )
                
                # Create display frame with annotations
                display_frame = self._create_display_frame(
                    frame, detections, qr_detections, identified_workers
                )
                
                self.current_display_frame = display_frame
                
                frame_count += 1
                
                # Small delay to prevent CPU overload
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error in detection loop: {e}")
                time.sleep(0.1)
    
    def _handle_violations(self, frame, detections, identified_workers, frame_count):
        """Handle detected violations with threshold and image capture limit"""
        current_time = time.time()
        threshold = getattr(self.config, 'VIOLATION_THRESHOLD', 3)
        max_frames_gap = 10  # Max frames between consecutive violations (about 0.3s at 30fps)
        
        # Track which workers have violations in this frame
        workers_with_violations = set()
        
        for violation in detections['violations']:
            violation_type = violation['type']
            
            # Try to match violation to identified worker
            matched_worker = None
            match_distance = float('inf')
            
            if identified_workers:
                v_bbox = violation['person_bbox']
                v_center_x = (v_bbox[0] + v_bbox[2]) / 2
                v_center_y = (v_bbox[1] + v_bbox[3]) / 2
                
                closest_worker = None
                min_distance = float('inf')
                
                for iw in identified_workers:
                    qr_bbox = iw['qr_bbox']
                    qr_center_x = qr_bbox['x'] + qr_bbox['width'] / 2
                    qr_center_y = qr_bbox['y'] + qr_bbox['height'] / 2
                    
                    # Calculate distance between person center and QR center
                    distance = ((v_center_x - qr_center_x) ** 2 + 
                               (v_center_y - qr_center_y) ** 2) ** 0.5
                    
                    # Also check if QR is inside person bounding box
                    qr_inside = (v_bbox[0] <= qr_center_x <= v_bbox[2] and 
                                v_bbox[1] <= qr_center_y <= v_bbox[3])
                    
                    if qr_inside:
                        # QR is inside person - strong match
                        distance = distance * 0.5  # Prefer inside matches
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_worker = iw['worker']
                
                # Accept match if QR is close (300 pixels) or inside person
                if min_distance < 300:
                    matched_worker = closest_worker
                    match_distance = min_distance
                    print(f"[MATCH] Worker {matched_worker['name']} matched with distance {min_distance:.1f}px")
            
            worker_key = matched_worker['employee_id'] if matched_worker else 'unknown'
            worker_name = matched_worker['name'] if matched_worker else 'Unknown'
            worker_id = matched_worker['id'] if matched_worker else None
            
            workers_with_violations.add(worker_key)
            
            # Check if this is a consecutive detection or a new violation sequence
            last_frame = self.last_frame_with_violation.get(worker_key, 0)
            frames_since_last = frame_count - last_frame
            
            if frames_since_last > max_frames_gap:
                # Too much time passed, reset counter
                self.violation_counters[worker_key] = 0
                print(f"Reset counter for {worker_name} (gap: {frames_since_last} frames)")
            
            # Update last frame seen
            self.last_frame_with_violation[worker_key] = frame_count
            
            # Increment counter
            if worker_key not in self.violation_counters:
                self.violation_counters[worker_key] = 0
            self.violation_counters[worker_key] += 1
            
            current_count = self.violation_counters[worker_key]
            
            # Check if we've reached the threshold
            if current_count < threshold:
                print(f"Counting violations for {worker_name}: {current_count}/{threshold}")
                continue  # Wait for more consecutive detections
            
            # Threshold reached! Reset counter and process violation
            self.violation_counters[worker_key] = 0
            
            print(f"THRESHOLD REACHED for {worker_name}! Alerting and capturing...")
            
            # Check cooldown for database/image operations
            last_violation_time = self.recent_violations.get(worker_key, 0)
            cooldown_active = (current_time - last_violation_time) < self.config.VIOLATION_COOLDOWN
            
            # ALWAYS play voice alert when threshold is reached
            print(f"[ALERT] Triggering voice alert for: {worker_name}")
            self.voice_alert.alert(
                worker_name=worker_name,
                violation_type=violation_type,
                worker_id=worker_key
            )
            
            # Only capture image and save to DB if not in cooldown
            if not cooldown_active:
                # Check if we should capture image (based on threshold)
                if worker_key not in self.image_capture_counters:
                    self.image_capture_counters[worker_key] = 0
                self.image_capture_counters[worker_key] += 1
                
                image_threshold = getattr(self.config, 'IMAGE_CAPTURE_THRESHOLD', 2)
                capture_image = self.image_capture_counters[worker_key] >= image_threshold
                
                image_filename = None
                if capture_image:
                    # Reset image counter
                    self.image_capture_counters[worker_key] = 0
                    
                    # Capture evidence (image only, no video)
                    evidence_data = self.evidence.capture_violation(
                        frame, worker_name, violation_type, capture_video=False
                    )
                    image_filename = evidence_data['image_filename']
                
                # Save to database
                violation_id = self.violation_model.create(
                    worker_id=worker_id,
                    violation_type=violation_type,
                    image_path=image_filename,
                    video_path=None,  # No video capture
                    zone=self.config.DEFAULT_ZONE,
                    confidence=violation['confidence']
                )
                
                # Create alert record
                alert_message = f"{violation_type} detected for {worker_name}"
                self.alert_model.create(
                    worker_id=worker_id,
                    violation_id=violation_id,
                    alert_message=alert_message
                )
                
                # Update cooldown
                self.recent_violations[worker_key] = current_time
                
                print(f"Violation recorded: {alert_message}" + (f" (Image captured)" if image_filename else " (No image)"))
            else:
                print(f"Alert for {worker_name}: {violation_type} (Cooldown active - no DB save)")
    
    def _create_display_frame(self, frame, detections, qr_detections, 
                              identified_workers):
        """Create annotated display frame"""
        # Draw PPE detections
        display_frame = self.detector.draw_detections(frame, detections)
        
        # Draw QR code detections
        display_frame = self.qr_scanner.draw_detections(display_frame, qr_detections)
        
        # Draw worker identification info
        for iw in identified_workers:
            worker = iw['worker']
            qr_bbox = iw['qr_bbox']
            
            # Draw worker name near QR code
            x = qr_bbox['x']
            y = qr_bbox['y'] - 30
            text = f"ID: {worker['name']}"
            
            cv2.putText(display_frame, text, (x, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw system info overlay
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(display_frame, f"InduSafe Sentinel | {timestamp}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw stats
        violation_count = len(detections['violations'])
        person_count = len(detections['persons'])
        status_color = (0, 0, 255) if violation_count > 0 else (0, 255, 0)
        status_text = f"Persons: {person_count} | Violations: {violation_count}"
        cv2.putText(display_frame, status_text, (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        
        return display_frame


def main():
    """Main entry point"""
    print("=" * 60)
    print("InduSafe Sentinel - Intelligent Worker-Aware")
    print("Industrial Safety & Compliance System")
    print("=" * 60)
    
    # Create and start detection system
    detection = DetectionSystem()
    
    if not detection.start():
        print("Failed to start detection system!")
        sys.exit(1)
    
    # Make detection system available to routes
    import app.routes as routes
    routes.detection_system = detection
    
    # Create Flask app
    app = create_app()
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        print("\nShutdown signal received...")
        detection.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\nStarting web server...")
    print("Access the dashboard at: http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    
    # Run Flask app
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        detection.stop()


if __name__ == '__main__':
    main()
