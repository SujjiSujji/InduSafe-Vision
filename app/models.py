"""
InduSafe Sentinel - Database Models
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Workers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                employee_id TEXT UNIQUE NOT NULL,
                qr_code TEXT UNIQUE NOT NULL,
                department TEXT DEFAULT 'General',
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Zones table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                risk_level TEXT DEFAULT 'Medium',
                camera_id TEXT DEFAULT 'cam_001'
            )
        ''')
        
        # Violations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                violation_type TEXT NOT NULL,
                image_path TEXT,
                video_path TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                zone TEXT DEFAULT 'Main Floor',
                status TEXT DEFAULT 'Open',
                confidence REAL,
                FOREIGN KEY (worker_id) REFERENCES workers (id)
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                violation_id INTEGER,
                alert_message TEXT NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT 0,
                FOREIGN KEY (worker_id) REFERENCES workers (id),
                FOREIGN KEY (violation_id) REFERENCES violations (id)
            )
        ''')
        
        # Insert default zone if not exists
        cursor.execute('SELECT COUNT(*) FROM zones')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO zones (name, risk_level, camera_id) 
                VALUES ('Main Floor', 'Medium', 'cam_001')
            ''')
        
        conn.commit()
        conn.close()


class Worker:
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, name: str, employee_id: str, qr_code: str, 
               department: str = 'General', email: str = None) -> int:
        """Create a new worker"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO workers (name, employee_id, qr_code, department, email)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, employee_id, qr_code, department, email))
        worker_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return worker_id
    
    def get_by_qr(self, qr_code: str) -> Optional[Dict]:
        """Get worker by QR code"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workers WHERE qr_code = ?', (qr_code,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_by_id(self, worker_id: int) -> Optional[Dict]:
        """Get worker by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workers WHERE id = ?', (worker_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_all(self) -> List[Dict]:
        """Get all workers"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workers ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_violation_count(self, worker_id: int) -> int:
        """Get violation count for a worker"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM violations WHERE worker_id = ?
        ''', (worker_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def delete(self, worker_id: int) -> bool:
        """Delete a worker and their associated records"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            # Delete associated alerts first
            cursor.execute('DELETE FROM alerts WHERE worker_id = ?', (worker_id,))
            # Delete associated violations
            cursor.execute('DELETE FROM violations WHERE worker_id = ?', (worker_id,))
            # Delete worker
            cursor.execute('DELETE FROM workers WHERE id = ?', (worker_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"Error deleting worker: {e}")
            return False


class Violation:
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, worker_id: Optional[int], violation_type: str,
               image_path: str = None, video_path: str = None,
               zone: str = 'Main Floor', confidence: float = 0.0) -> int:
        """Create a new violation record"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO violations (worker_id, violation_type, image_path, 
                                   video_path, zone, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (worker_id, violation_type, image_path, video_path, zone, confidence))
        violation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return violation_id
    
    def get_all(self, limit: int = 100) -> List[Dict]:
        """Get all violations with worker info"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.*, w.name as worker_name, w.employee_id 
            FROM violations v
            LEFT JOIN workers w ON v.worker_id = w.id
            ORDER BY v.timestamp DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_by_id(self, violation_id: int) -> Optional[Dict]:
        """Get violation by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.*, w.name as worker_name, w.employee_id, w.department
            FROM violations v
            LEFT JOIN workers w ON v.worker_id = w.id
            WHERE v.id = ?
        ''', (violation_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_stats(self) -> Dict:
        """Get violation statistics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Total violations
        cursor.execute('SELECT COUNT(*) FROM violations')
        total = cursor.fetchone()[0]
        
        # Today's violations
        cursor.execute('''
            SELECT COUNT(*) FROM violations 
            WHERE date(timestamp) = date('now')
        ''')
        today = cursor.fetchone()[0]
        
        # Open violations
        cursor.execute('''
            SELECT COUNT(*) FROM violations WHERE status = 'Open'
        ''')
        open_count = cursor.fetchone()[0]
        
        # Zone-wise count
        cursor.execute('''
            SELECT zone, COUNT(*) as count FROM violations 
            GROUP BY zone ORDER BY count DESC
        ''')
        zones = [dict(row) for row in cursor.fetchall()]
        
        # Top violators
        cursor.execute('''
            SELECT w.name, COUNT(*) as count 
            FROM violations v
            JOIN workers w ON v.worker_id = w.id
            GROUP BY v.worker_id
            ORDER BY count DESC
            LIMIT 5
        ''')
        top_violators = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total': total,
            'today': today,
            'open': open_count,
            'zones': zones,
            'top_violators': top_violators
        }
    
    def acknowledge(self, violation_id: int) -> bool:
        """Acknowledge a violation"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE violations SET status = 'Acknowledged' WHERE id = ?
        ''', (violation_id,))
        conn.commit()
        conn.close()
        return True


class Alert:
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, worker_id: Optional[int], violation_id: Optional[int],
               alert_message: str) -> int:
        """Create a new alert"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (worker_id, violation_id, alert_message)
            VALUES (?, ?, ?)
        ''', (worker_id, violation_id, alert_message))
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return alert_id
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.*, w.name as worker_name
            FROM alerts a
            LEFT JOIN workers w ON a.worker_id = w.id
            ORDER BY a.alert_time DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class Zone:
    def __init__(self, db: Database):
        self.db = db
    
    def get_all(self) -> List[Dict]:
        """Get all zones"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM zones')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
