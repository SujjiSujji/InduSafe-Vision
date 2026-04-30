"""
InduSafe Sentinel - Voice Alert System
Reliable voice alerts using pyttsx3 with proper Windows support
"""
import pyttsx3
import threading
import time
from typing import Optional


class VoiceAlert:
    def __init__(self, volume: float = 0.9, rate: int = 150, enabled: bool = True):
        self.enabled = enabled
        self.volume = volume
        self.rate = rate
        self.last_alert_time = {}
        self.min_time_between_alerts = 2  # Minimum 2 seconds between alerts
        
        # Test engine on init
        if self.enabled:
            try:
                engine = pyttsx3.init()
                engine.setProperty('volume', volume)
                engine.setProperty('rate', rate)
                voices = engine.getProperty('voices')
                if voices:
                    engine.setProperty('voice', voices[0].id)
                engine.say("Voice alert system ready")
                engine.runAndWait()
                engine.stop()
                print("[VOICE] Voice alert system initialized and tested successfully")
            except Exception as e:
                print(f"[VOICE ERROR] Failed to initialize: {e}")
                self.enabled = False
    
    def alert(self, worker_name: str, violation_type: str, worker_id: str = None):
        """
        Play voice alert immediately
        """
        if not self.enabled:
            print("[VOICE] Voice alerts disabled")
            return
        
        # Format message
        violation_text = violation_type.replace('_', ' ').title()
        
        # Use worker name if available, otherwise generic
        if worker_name and worker_name != 'Unknown':
            message = f"Warning {worker_name}, {violation_text}!"
        else:
            message = f"Warning! {violation_text} detected!"
        
        # Check minimum time between alerts for same worker
        current_time = time.time()
        worker_key = worker_id or worker_name or 'unknown'
        last_time = self.last_alert_time.get(worker_key, 0)
        
        if current_time - last_time < self.min_time_between_alerts:
            print(f"[VOICE] Skipping alert for {worker_name} - too soon")
            return
        
        self.last_alert_time[worker_key] = current_time
        
        # Play alert in separate thread to not block
        alert_thread = threading.Thread(target=self._speak, args=(message, worker_name))
        alert_thread.daemon = True
        alert_thread.start()
    
    def _speak(self, message: str, worker_name: str):
        """Speak the message"""
        try:
            print(f"[VOICE] Speaking: {message}")
            
            # Create fresh engine instance for each alert
            engine = pyttsx3.init()
            engine.setProperty('volume', self.volume)
            engine.setProperty('rate', self.rate)
            
            # Try to use a clear voice
            voices = engine.getProperty('voices')
            if voices:
                # Prefer English voices
                for voice in voices:
                    if 'english' in voice.name.lower() or 'en-us' in voice.id.lower():
                        engine.setProperty('voice', voice.id)
                        break
                else:
                    engine.setProperty('voice', voices[0].id)
            
            # Speak
            engine.say(message)
            engine.runAndWait()
            engine.stop()
            
            print(f"[VOICE] Completed alert for: {worker_name}")
            
        except Exception as e:
            print(f"[VOICE ERROR] {e}")
    
    def test_alert(self):
        """Test the voice alert system"""
        self.alert("Test Worker", "hard_hat_missing", "test")
