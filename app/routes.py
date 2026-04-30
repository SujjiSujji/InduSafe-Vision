"""
InduSafe Sentinel - Flask Routes
"""
from flask import Blueprint, render_template, jsonify, request, Response, current_app
import cv2
import numpy as np
import io
import base64
import qrcode
from PIL import Image
from .models import Database, Worker, Violation, Alert, Zone

main_bp = Blueprint('main', __name__)

# Global detection system reference (set by run.py)
detection_system = None

def get_db():
    """Get database instance"""
    return Database(current_app.config['DATABASE_PATH'])


@main_bp.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


@main_bp.route('/workers')
def workers_page():
    """Worker management page"""
    return render_template('workers.html')


@main_bp.route('/violations')
def violations_page():
    """All violations page"""
    return render_template('violations.html')

@main_bp.route('/violations/<int:violation_id>')
def violation_detail(violation_id):
    """Violation detail page"""
    return render_template('violation_detail.html', violation_id=violation_id)


# API Routes

@main_bp.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    db = get_db()
    violation_model = Violation(db)
    stats = violation_model.get_stats()
    return jsonify(stats)


@main_bp.route('/api/workers', methods=['GET', 'POST'])
def workers_api():
    """Worker API endpoints"""
    db = get_db()
    worker_model = Worker(db)
    
    if request.method == 'GET':
        workers = worker_model.get_all()
        # Add violation count for each worker
        for worker in workers:
            worker['violation_count'] = worker_model.get_violation_count(worker['id'])
        return jsonify(workers)
    
    elif request.method == 'POST':
        data = request.json
        try:
            worker_id = worker_model.create(
                name=data['name'],
                employee_id=data['employee_id'],
                qr_code=data.get('qr_code', data['employee_id']),
                department=data.get('department', 'General'),
                email=data.get('email')
            )
            return jsonify({'success': True, 'id': worker_id}), 201
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400


@main_bp.route('/api/workers/<int:worker_id>')
def get_worker(worker_id):
    """Get single worker details"""
    db = get_db()
    worker_model = Worker(db)
    worker = worker_model.get_by_id(worker_id)
    
    if worker:
        worker['violation_count'] = worker_model.get_violation_count(worker_id)
        return jsonify(worker)
    
    return jsonify({'error': 'Worker not found'}), 404


@main_bp.route('/api/workers/<int:worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    """Delete a worker"""
    db = get_db()
    worker_model = Worker(db)
    
    # Check if worker exists
    worker = worker_model.get_by_id(worker_id)
    if not worker:
        return jsonify({'success': False, 'error': 'Worker not found'}), 404
    
    # Delete worker
    if worker_model.delete(worker_id):
        return jsonify({'success': True, 'message': 'Worker deleted successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to delete worker'}), 500


@main_bp.route('/api/workers/<int:worker_id>/qrcode')
def generate_worker_qr(worker_id):
    """Generate QR code for worker"""
    db = get_db()
    worker_model = Worker(db)
    worker = worker_model.get_by_id(worker_id)
    
    if not worker:
        return jsonify({'error': 'Worker not found'}), 404
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"WORKER:{worker['employee_id']}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return Response(img_io.getvalue(), mimetype='image/png')


@main_bp.route('/api/violations', methods=['GET'])
def get_violations():
    """Get violation history"""
    db = get_db()
    violation_model = Violation(db)
    limit = request.args.get('limit', 100, type=int)
    violations = violation_model.get_all(limit=limit)
    return jsonify(violations)


@main_bp.route('/api/violations/<int:violation_id>', methods=['GET'])
def get_violation(violation_id):
    """Get single violation details"""
    db = get_db()
    violation_model = Violation(db)
    violation = violation_model.get_by_id(violation_id)
    
    if violation:
        return jsonify(violation)
    
    return jsonify({'error': 'Violation not found'}), 404


@main_bp.route('/api/violations/<int:violation_id>/acknowledge', methods=['POST'])
def acknowledge_violation(violation_id):
    """Acknowledge a violation"""
    db = get_db()
    violation_model = Violation(db)
    
    try:
        violation_model.acknowledge(violation_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@main_bp.route('/api/alerts/recent')
def get_recent_alerts():
    """Get recent alerts"""
    db = get_db()
    alert_model = Alert(db)
    limit = request.args.get('limit', 10, type=int)
    alerts = alert_model.get_recent(limit=limit)
    return jsonify(alerts)


@main_bp.route('/api/live-feed')
def live_feed():
    """Live camera feed (MJPEG stream)"""
    def generate():
        while True:
            if detection_system and detection_system.current_display_frame is not None:
                frame = detection_system.current_display_frame
                
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            import time
            time.sleep(0.033)  # ~30 fps
    
    return Response(generate(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@main_bp.route('/api/snapshot')
def get_snapshot():
    """Get current camera snapshot as base64"""
    if detection_system and detection_system.current_display_frame is not None:
        frame = detection_system.current_display_frame
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            return jsonify({'image': f'data:image/jpeg;base64,{img_base64}'})
    
    return jsonify({'error': 'No frame available'}), 503


@main_bp.route('/api/zones')
def get_zones():
    """Get all zones"""
    db = get_db()
    zone_model = Zone(db)
    zones = zone_model.get_all()
    return jsonify(zones)


@main_bp.route('/api/system/status')
def system_status():
    """Get system status"""
    status = {
        'camera_active': detection_system.camera.is_active() if detection_system else False,
        'detection_running': detection_system.is_running if detection_system else False,
        'voice_alerts_enabled': current_app.config.get('VOICE_ALERT_ENABLED', True),
        'camera_enabled': detection_system.camera_enabled if detection_system else True
    }
    return jsonify(status)


@main_bp.route('/api/camera/toggle', methods=['POST'])
def toggle_camera():
    """Toggle camera on/off"""
    if detection_system:
        detection_system.camera_enabled = not detection_system.camera_enabled
        return jsonify({
            'success': True, 
            'camera_enabled': detection_system.camera_enabled
        })
    return jsonify({'success': False, 'error': 'Detection system not running'}), 503



