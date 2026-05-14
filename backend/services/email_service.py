import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from models.schemas import PREvent, ReviewResult

def send_review_email(pr_event: PREvent, review: ReviewResult, to_email: str) -> bool:
    """
    Formats the AI review and sends it as an HTML email.
    If no SMTP credentials are provided in the environment, it mocks the email by logging to the console.
    """
    subject = f"[CodeSense] Review Completed: PR #{pr_event.pr_number} - {pr_event.pr_title}"
    
    html_body = _generate_html_body(pr_event, review)
    
    # Check for SMTP credentials
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", 587)
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_server or not smtp_user or not smtp_password:
        print("\n" + "="*50)
        print("📧 [MOCK EMAIL] Email triggered but no SMTP credentials found.")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("Body (HTML truncated):")
        print(html_body[:300] + "...\n")
        print("="*50 + "\n")
        return True
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"CodeSense <{smtp_user}>"
        msg["To"] = to_email
        
        # Attach HTML body
        part = MIMEText(html_body, "html")
        msg.attach(part)
        
        # Send email based on port
        if int(smtp_port) == 465:
            server = smtplib.SMTP_SSL(smtp_server, int(smtp_port))
            server.login(smtp_user, smtp_password)
        else:
            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(smtp_user, smtp_password)
            
        server.sendmail(msg["From"], to_email, msg.as_string())
        server.quit()
        
        print(f"[EMAIL SENT] Review summary sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email: {e}")
        return False

def _generate_html_body(pr_event: PREvent, review: ReviewResult) -> str:
    """Generates the HTML payload for the review email."""
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>🤖 CodeSense AI Review</h2>
        <p>Your Pull Request <strong>#{pr_event.pr_number} ({pr_event.pr_title})</strong> on repository <strong>{pr_event.repo_full_name}</strong> has been analyzed.</p>
        
        <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <p style="margin: 0;"><strong>Summary:</strong> {review.summary}</p>
        </div>
        
        <h3>📊 Severity Breakdown</h3>
        <ul>
            <li>🔴 <strong>Critical:</strong> {review.total_critical}</li>
            <li>🟡 <strong>Warning:</strong> {review.total_warnings}</li>
            <li>🔵 <strong>Info:</strong> {review.total_info}</li>
        </ul>
        
        <h3>📝 Findings Overview</h3>
    """
    
    if not review.findings:
        html += "<p>No issues found! Great job. 🎉</p>"
    else:
        html += "<ul>"
        for f in review.findings:
            icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity.value, "⚪")
            html += f"<li style='margin-bottom: 10px;'>{icon} <strong>{f.title}</strong> (<code>{f.file}:{f.line}</code>)<br>{f.explanation}</li>"
        html += "</ul>"
        
    html += """
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #888;">Powered by CodeSense Automated Code Review</p>
    </body>
    </html>
    """
    return html
