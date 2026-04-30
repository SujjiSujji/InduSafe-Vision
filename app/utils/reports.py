"""
InduSafe Sentinel - Email Reporting System
Sends session summary reports via email
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict
import os


class EmailReporter:
    def __init__(self, smtp_server: str = None, smtp_port: int = None, 
                 username: str = None, password: str = None, 
                 from_email: str = None, config=None):
        # Use config values if provided, otherwise use environment variables or defaults
        if config:
            self.smtp_server = smtp_server or config.SMTP_SERVER
            self.smtp_port = smtp_port or config.SMTP_PORT
            self.username = username or config.SMTP_USERNAME or os.environ.get('SMTP_USERNAME', '')
            self.password = password or config.SMTP_PASSWORD or os.environ.get('SMTP_PASSWORD', '')
            self.supervisor_email = config.SUPERVISOR_EMAIL
        else:
            self.smtp_server = smtp_server or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            self.smtp_port = smtp_port or int(os.environ.get('SMTP_PORT', 587))
            self.username = username or os.environ.get('SMTP_USERNAME', '')
            self.password = password or os.environ.get('SMTP_PASSWORD', '')
            self.supervisor_email = os.environ.get('SUPERVISOR_EMAIL', '')
        
        self.from_email = from_email or self.username
        self.enabled = bool(self.username and self.password)
        
    def generate_session_report(self, session_start: datetime, 
                                violations: List[Dict],
                                workers: List[Dict]) -> str:
        """Generate HTML report for the session"""
        
        session_end = datetime.now()
        duration = session_end - session_start
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        total_violations = len(violations)
        unique_workers = len(set(v['worker_id'] for v in violations if v.get('worker_id')))
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #1a237e; color: white; padding: 20px; text-align: center; }}
                .summary {{ background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat-box {{ background: white; padding: 15px; border-radius: 5px; text-align: center; border: 1px solid #ddd; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #1a237e; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #1a237e; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>InduSafe Sentinel - Session Report</h1>
                <p>Industrial Safety & Compliance System</p>
            </div>
            
            <div class="summary">
                <h2>Session Summary</h2>
                <p><strong>Session Start:</strong> {session_start.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Session End:</strong> {session_end.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Duration:</strong> {hours}h {minutes}m {seconds}s</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{total_violations}</div>
                    <div>Total Violations</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{unique_workers}</div>
                    <div>Workers Involved</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{len(workers)}</div>
                    <div>Registered Workers</div>
                </div>
            </div>
            
            <h2>Violation Details</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Worker</th>
                    <th>Violation Type</th>
                    <th>Zone</th>
                    <th>Status</th>
                </tr>
        """
        
        for v in violations[:50]:  # Limit to 50 violations in email
            worker_name = v.get('worker_name', 'Unknown')
            html += f"""
                <tr>
                    <td>{v.get('timestamp', 'N/A')}</td>
                    <td>{worker_name}</td>
                    <td>{v.get('violation_type', 'N/A').replace('_', ' ').title()}</td>
                    <td>{v.get('zone', 'N/A')}</td>
                    <td>{v.get('status', 'N/A')}</td>
                </tr>
            """
        
        if len(violations) > 50:
            html += f"<tr><td colspan='5' style='text-align:center;'>... and {len(violations) - 50} more violations</td></tr>"
        
        html += """
            </table>
            
            <div class="footer">
                <p>Generated by InduSafe Sentinel</p>
                <p>This is an automated report. Please do not reply to this email.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_report(self, to_email: str, subject: str, html_content: str) -> bool:
        """Send email report"""
        if not self.enabled:
            print("[EMAIL] Email not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.")
            print("[EMAIL] Report would have been sent to:", to_email)
            print("[EMAIL] Report preview saved to console.")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Attach HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            print(f"[EMAIL] Report sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send email: {e}")
            return False
    
    def send_session_report(self, to_email: str, session_start: datetime,
                           violations: List[Dict], workers: List[Dict]) -> bool:
        """Generate and send session report"""
        html = self.generate_session_report(session_start, violations, workers)
        subject = f"InduSafe Sentinel - Session Report ({datetime.now().strftime('%Y-%m-%d')})"
        return self.send_report(to_email, subject, html)
    
    def generate_worker_report(self, worker: Dict, violations: List[Dict]) -> str:
        """Generate individual report for a worker"""
        worker_name = worker.get('name', 'Unknown')
        worker_email = worker.get('email', 'No email')
        worker_id = worker.get('employee_id', 'N/A')
        department = worker.get('department', 'General')
        
        total_violations = len(violations)
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #d32f2f; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .stats {{ background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #d32f2f; color: white; padding: 10px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Safety Violation Report</h1>
                <p>InduSafe Sentinel - Industrial Safety System</p>
            </div>
            
            <div class="content">
                <p>Dear <strong>{worker_name}</strong>,</p>
                
                <div class="warning">
                    <strong>⚠️ Safety Notice</strong>
                    <p>This report contains information about PPE violations detected during your work session today.</p>
                </div>
                
                <div class="stats">
                    <h3>Your Details</h3>
                    <p><strong>Name:</strong> {worker_name}</p>
                    <p><strong>Employee ID:</strong> {worker_id}</p>
                    <p><strong>Department:</strong> {department}</p>
                    <p><strong>Total Violations Today:</strong> {total_violations}</p>
                </div>
                
                <h3>Violation Details</h3>
                <table>
                    <tr>
                        <th>Time</th>
                        <th>Violation Type</th>
                        <th>Zone</th>
                        <th>Status</th>
                    </tr>
        """
        
        for v in violations:
            html += f"""
                    <tr>
                        <td>{v.get('timestamp', 'N/A')}</td>
                        <td>{v.get('violation_type', 'N/A').replace('_', ' ').title()}</td>
                        <td>{v.get('zone', 'N/A')}</td>
                        <td>{v.get('status', 'N/A')}</td>
                    </tr>
            """
        
        html += """
                </table>
                
                <div class="warning">
                    <strong>⚠️ Important Reminder</strong>
                    <p>Please ensure you wear proper PPE (Personal Protective Equipment) at all times while in the work zone. This includes:</p>
                    <ul>
                        <li>Hard Hat / Safety Helmet</li>
                        <li>Safety Vest</li>
                        <li>Safety Shoes</li>
                        <li>Other required PPE for your specific work area</li>
                    </ul>
                    <p>Your safety is our priority. Thank you for your cooperation.</p>
                </div>
            </div>
            
            <div class="footer">
                <p>Generated by InduSafe Sentinel</p>
                <p>This is an automated safety report. Please do not reply to this email.</p>
                <p>If you have questions, please contact your supervisor.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_worker_reports(self, workers: List[Dict], all_violations: List[Dict]) -> Dict:
        """Send individual reports to all workers with violations"""
        results = {'sent': 0, 'failed': 0, 'skipped': 0, 'details': []}
        
        for worker in workers:
            worker_email = worker.get('email')
            worker_id = worker.get('id')
            worker_name = worker.get('name', 'Unknown')
            
            # Skip workers without email
            if not worker_email:
                results['skipped'] += 1
                results['details'].append({'worker': worker_name, 'status': 'skipped', 'reason': 'No email'})
                continue
            
            # Get violations for this worker
            worker_violations = [v for v in all_violations if v.get('worker_id') == worker_id]
            
            # Skip if no violations
            if not worker_violations:
                results['skipped'] += 1
                results['details'].append({'worker': worker_name, 'status': 'skipped', 'reason': 'No violations'})
                continue
            
            # Generate and send report
            html = self.generate_worker_report(worker, worker_violations)
            subject = f"Safety Violation Report - {worker_name} ({datetime.now().strftime('%Y-%m-%d')})"
            
            if self.send_report(worker_email, subject, html):
                results['sent'] += 1
                results['details'].append({'worker': worker_name, 'status': 'sent', 'email': worker_email})
            else:
                results['failed'] += 1
                results['details'].append({'worker': worker_name, 'status': 'failed', 'email': worker_email})
        
        return results
