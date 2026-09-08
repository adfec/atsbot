"""
Entrega por email (SMTP), canal elegido para esta versión. Igual que el
artículo original, pensado para Gmail SMTP con app password, pero
funciona con cualquier proveedor SMTP estándar via variables de entorno.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _render_job_row(job) -> str:
    role_label = (job.matched_role or "sin categoría").replace("_", " ").title()
    return (
        f"<li><b>{job.title}</b> — {job.company} "
        f"<span style='color:#666'>({job.location or 'ubicación no especificada'})</span><br>"
        f"<span style='font-size:12px;color:#888'>{role_label} · score {job.score} · vía {job.ats}</span><br>"
        f"<a href='{job.url}'>{job.url}</a></li>"
    )


def render_digest_html(company_jobs: list, role_search_jobs: list, alarms: list) -> str:
    parts = ["<html><body style='font-family:sans-serif'>"]

    if alarms:
        parts.append("<div style='background:#fff3cd;padding:10px;margin-bottom:16px'>")
        parts.append("<b>⚠ Alarmas de salud de fuente</b><ul>")
        parts.extend(f"<li>{a}</li>" for a in alarms)
        parts.append("</ul></div>")

    parts.append(f"<h2>Vacantes nuevas — empresas objetivo ({len(company_jobs)})</h2>")
    if company_jobs:
        parts.append("<ul>" + "".join(_render_job_row(j) for j in company_jobs) + "</ul>")
    else:
        parts.append("<p>Sin novedades hoy en la lista de empresas.</p>")

    parts.append(f"<h2>Búsqueda por rol — fuente abierta ({len(role_search_jobs)})</h2>")
    parts.append(
        "<p style='color:#666;font-size:13px'>Estas vacantes vienen de agregadores "
        "públicos filtrados solo por título/keyword, no por una lista de empresas "
        "verificadas. La relevancia y compatibilidad quedan a tu criterio.</p>"
    )
    if role_search_jobs:
        parts.append("<ul>" + "".join(_render_job_row(j) for j in role_search_jobs) + "</ul>")
    else:
        parts.append("<p>Sin novedades hoy en búsqueda por rol.</p>")

    parts.append("</body></html>")
    return "".join(parts)


def send_email(subject: str, html_body: str):
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr = os.environ.get("ALERT_TO", smtp_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
