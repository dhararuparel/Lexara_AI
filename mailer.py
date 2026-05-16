"""
Email helper — uses Flask-Mail with SMTP.
Configure via .env: MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM
"""
import os
from flask_mail import Mail, Message

mail = Mail()

def init_mail(app):
    app.config["MAIL_SERVER"]   = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"]     = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]  = True
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_FROM", os.getenv("MAIL_USERNAME", "noreply@lexara.ai"))
    mail.init_app(app)

def send_verification_email(to_email: str, name: str, token: str, base_url: str):
    link = f"{base_url}api/auth/verify-email?token={token}"
    msg = Message("Verify your Lexara AI account", recipients=[to_email])
    msg.html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:2rem;background:#0f172a;color:#f8fafc;border-radius:12px">
      <h2 style="color:#8b5cf6;margin-bottom:.5rem">Welcome to Lexara AI, {name}!</h2>
      <p style="color:#94a3b8;margin-bottom:1.5rem">Click the button below to verify your email address.</p>
      <a href="{link}" style="display:inline-block;padding:.75rem 1.5rem;background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Verify Email</a>
      <p style="color:#64748b;font-size:.8rem;margin-top:1.5rem">Link expires in 24 hours. If you didn't sign up, ignore this email.</p>
    </div>"""
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[Mail] Failed to send verification email: {e}")
        return False

def send_workspace_invite_email(to_email: str, inviter_name: str, workspace_name: str, role: str, token: str, base_url: str):
    link = f"{base_url}workspace-invite?token={token}"
    msg = Message(f"You're invited to join '{workspace_name}' on Lexara AI", recipients=[to_email])
    msg.html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:2rem;background:#0f172a;color:#f8fafc;border-radius:12px">
      <div style="text-align:center;margin-bottom:1.5rem">
        <div style="width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#7c3aed,#8b5cf6);display:inline-flex;align-items:center;justify-content:center;font-size:1.5rem">🏢</div>
      </div>
      <h2 style="color:#8b5cf6;margin-bottom:.4rem;text-align:center">Workspace Invitation</h2>
      <p style="color:#94a3b8;text-align:center;margin-bottom:1.5rem">
        <strong style="color:#f8fafc">{inviter_name}</strong> has invited you to join
        <strong style="color:#f8fafc">{workspace_name}</strong> as a
        <span style="color:#a78bfa;font-weight:600">{role}</span>.
      </p>
      <div style="text-align:center;margin-bottom:1.5rem">
        <a href="{link}" style="display:inline-block;padding:.8rem 2rem;background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;border-radius:10px;text-decoration:none;font-weight:600;font-size:.95rem">
          Accept Invitation
        </a>
      </div>
      <p style="color:#64748b;font-size:.78rem;text-align:center">
        This invitation link expires in 7 days.<br/>
        If you don't have a Lexara AI account, you'll be prompted to create one.
      </p>
    </div>"""
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[Mail] Failed to send workspace invite email: {e}")
        return False


def send_reset_email(to_email: str, name: str, token: str, base_url: str):
    link = f"{base_url}reset-password?token={token}"
    msg = Message("Reset your Lexara AI password", recipients=[to_email])
    msg.html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:2rem;background:#0f172a;color:#f8fafc;border-radius:12px">
      <h2 style="color:#8b5cf6;margin-bottom:.5rem">Password Reset</h2>
      <p style="color:#94a3b8;margin-bottom:1.5rem">Hi {name}, click below to reset your password.</p>
      <a href="{link}" style="display:inline-block;padding:.75rem 1.5rem;background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Reset Password</a>
      <p style="color:#64748b;font-size:.8rem;margin-top:1.5rem">Link expires in 1 hour. If you didn't request this, ignore this email.</p>
    </div>"""
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[Mail] Failed to send reset email: {e}")
        return False
