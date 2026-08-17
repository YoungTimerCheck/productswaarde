import os
import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field

from scraper.analyzer import analyze_listing
from scraper.marktplaats import supabase

router = APIRouter()

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
BASE_URL = os.environ.get("BASE_URL", "https://productswaarde.nl")


def _unsubscribe_url(token: str) -> str:
    return f"{BASE_URL}/api/alerts/unsubscribe/{token}"


def _send_email(to: str, subject: str, html_body: str, text_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def _email_wrapper(inner_html: str) -> str:
    return f"""\
<!doctype html>
<html lang="nl">
<body style="margin:0;padding:0;background-color:#f9fafb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:20px 32px;border-bottom:1px solid #e5e7eb;">
              <span style="font-size:18px;font-weight:bold;color:#111827;">Products<span style="color:#059669;">waarde</span></span>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              {inner_html}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_confirmation_email(alert: dict) -> None:
    keyword = alert["keyword"]
    max_price = alert["max_price"]
    unsubscribe_url = _unsubscribe_url(alert["unsubscribe_token"])

    subject = f"✅ Prijsalert aangemaakt — {keyword}"

    inner_html = f"""
      <h1 style="font-size:18px;margin:0 0 12px;">Prijsalert aangemaakt</h1>
      <p style="font-size:14px;line-height:1.6;color:#374151;margin:0 0 16px;">
        Je ontvangt een melding zodra er een advertentie verschijnt voor
        <strong>'{keyword}'</strong> onder <strong>€{max_price:.0f}</strong>.
      </p>
      <p style="font-size:12px;color:#9ca3af;margin:24px 0 0;">
        <a href="{unsubscribe_url}" style="color:#9ca3af;">Uitschrijven</a>
      </p>
    """
    html_body = _email_wrapper(inner_html)

    text_body = (
        "Prijsalert aangemaakt\n\n"
        f"Je ontvangt een melding zodra er een advertentie verschijnt voor '{keyword}' "
        f"onder €{max_price:.0f}.\n\n"
        f"Uitschrijven: {unsubscribe_url}\n"
    )

    _send_email(alert["email"], subject, html_body, text_body)


def send_match_email(alert: dict, listing: dict, median_price: float | None = None) -> None:
    analyzed = analyze_listing(listing, median_price)
    deal_score = analyzed.get("deal_score") or ""
    price = listing["price"]

    subject = f"🎯 Nieuwe deal: {listing['title']} voor €{price:.0f}"
    unsubscribe_url = _unsubscribe_url(alert["unsubscribe_token"])

    image_html = (
        f'<img src="{listing["image_url"]}" alt="" style="width:100%;border-radius:8px;margin-bottom:16px;display:block;" />'
        if listing.get("image_url")
        else ""
    )
    facts = " · ".join(filter(None, [listing.get("condition"), listing.get("location")]))

    inner_html = f"""
      {image_html}
      <h1 style="font-size:16px;margin:0 0 8px;">{listing['title']}</h1>
      <p style="font-size:22px;font-weight:bold;color:#059669;margin:0 0 8px;">€{price:.0f}</p>
      {f'<p style="font-size:13px;margin:0 0 12px;">{deal_score}</p>' if deal_score else ""}
      {f'<p style="font-size:13px;color:#6b7280;margin:0 0 20px;">{facts}</p>' if facts else ""}
      <a href="{listing['url']}" style="display:inline-block;background-color:#059669;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:8px;font-weight:bold;font-size:14px;">Bekijk op Marktplaats →</a>
      <p style="font-size:12px;color:#9ca3af;margin:24px 0 0;">
        <a href="{unsubscribe_url}" style="color:#9ca3af;">Uitschrijven</a>
      </p>
    """
    html_body = _email_wrapper(inner_html)

    text_body = (
        f"Nieuwe deal: {listing['title']}\n"
        f"Prijs: €{price:.0f}\n"
        f"{deal_score}\n\n"
        f"Bekijk op Marktplaats: {listing['url']}\n\n"
        f"Uitschrijven: {unsubscribe_url}\n"
    )

    _send_email(alert["email"], subject, html_body, text_body)

UNSUBSCRIBE_PAGE = """<!doctype html>
<html lang="nl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title} | Productswaarde</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 min-h-screen flex items-center justify-center px-4">
  <div class="max-w-md w-full bg-white border border-gray-200 shadow-sm rounded-xl p-8 text-center">
    <div class="text-4xl" aria-hidden="true">{icon}</div>
    <h1 class="mt-3 text-xl font-bold text-gray-900">{title}</h1>
    <p class="mt-2 text-sm text-gray-600">{message}</p>
    <a href="/" class="mt-6 inline-block rounded-lg bg-emerald-600 px-6 py-2.5 font-semibold text-white hover:bg-emerald-700 transition-colors">Terug naar Productswaarde</a>
  </div>
</body>
</html>"""

MAX_FREE_ALERTS = 2
UPGRADE_MESSAGE = (
    "Je hebt het maximum van 2 gratis prijsalerts bereikt. "
    "Upgrade naar Pro (€2,99/maand) voor onbeperkte alerts."
)


class AlertCreate(BaseModel):
    keyword: str = Field(min_length=1)
    max_price: float = Field(gt=0)
    email: EmailStr


@router.post("/api/alerts")
def create_alert(payload: AlertCreate):
    keyword = payload.keyword.strip().lower()
    email = str(payload.email).strip().lower()

    active_alerts = (
        supabase.table("alerts")
        .select("id", count="exact")
        .eq("email", email)
        .eq("active", True)
        .execute()
    )
    if (active_alerts.count or 0) >= MAX_FREE_ALERTS:
        raise HTTPException(status_code=403, detail=UPGRADE_MESSAGE)

    inserted = (
        supabase.table("alerts")
        .insert({"keyword": keyword, "max_price": payload.max_price, "email": email})
        .execute()
    )
    alert = inserted.data[0]

    try:
        send_confirmation_email(alert)
    except Exception as exc:
        # The alert itself was created successfully; a failed confirmation email
        # shouldn't fail the request. Log and continue.
        print(f"Failed to send confirmation email for alert {alert['id']}: {exc}")

    return {
        "id": alert["id"],
        "keyword": alert["keyword"],
        "max_price": alert["max_price"],
        "unsubscribe_token": alert["unsubscribe_token"],
        "message": f"Prijsalert aangemaakt voor '{alert['keyword']}' onder €{alert['max_price']:.0f}.",
    }


@router.get("/api/alerts/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str):
    result = (
        supabase.table("alerts")
        .update({"active": False})
        .eq("unsubscribe_token", token)
        .execute()
    )

    if not result.data:
        return HTMLResponse(
            UNSUBSCRIBE_PAGE.format(
                icon="⚠️",
                title="Ongeldige link",
                message="Deze uitschrijflink is niet geldig of al verwerkt.",
            ),
            status_code=404,
        )

    return HTMLResponse(
        UNSUBSCRIBE_PAGE.format(
            icon="✅",
            title="Je bent uitgeschreven",
            message="Je ontvangt geen meldingen meer voor deze zoekopdracht.",
        )
    )
