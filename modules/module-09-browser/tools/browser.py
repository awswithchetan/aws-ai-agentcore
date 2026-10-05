"""Browser-backed carrier tracking for Aria."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import quote_plus

import boto3
from bedrock_agentcore.tools.browser_client import browser_session
from playwright.async_api import async_playwright
from strands import tool

from config import cfg

logger = logging.getLogger(__name__)

# Presigned screenshot links stay valid for 15 minutes — long enough for a
# customer to open the image, short enough to limit exposure.
_SCREENSHOT_URL_TTL_SECONDS = 900

_s3_client = boto3.client("s3", region_name=cfg.region)


def _upload_screenshot(png_bytes: bytes, tracking_number: str) -> str:
    """Upload a screenshot to the private bucket and return a presigned URL.

    Returns an empty string if screenshots are not configured or the upload
    fails — screenshot capture is best-effort and must never break tracking.
    """
    if not cfg.screenshot_bucket:
        return ""

    safe_tracking = quote_plus(tracking_number)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"carrier-screenshots/{safe_tracking}/{timestamp}-{uuid.uuid4().hex[:8]}.png"

    try:
        _s3_client.put_object(
            Bucket=cfg.screenshot_bucket,
            Key=key,
            Body=png_bytes,
            ContentType="image/png",
        )
        return _s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": cfg.screenshot_bucket, "Key": key},
            ExpiresIn=_SCREENSHOT_URL_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Screenshot upload failed: %s", exc, exc_info=True)
        return ""


async def _lookup_tracking(tracking_number: str) -> str:
    """Use a managed AgentCore Browser session to query the carrier portal."""
    url = f"{cfg.carrier_tracking_url}?trackingNumber={quote_plus(tracking_number)}"

    with browser_session(cfg.region) as client:
        ws_url, headers = client.generate_ws_headers()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                ws_url,
                headers=headers,
            )
            try:
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_function(
                    "document.querySelector('#tracking-result')?.dataset.loaded === 'true'",
                    timeout=10000,
                )

                status = await page.locator("#tracking-status").inner_text()
                carrier = await page.locator("#tracking-carrier").inner_text()
                location = await page.locator("#tracking-location").inner_text()
                estimate = await page.locator("#tracking-estimate").inner_text()
                detail = await page.locator("#tracking-detail").inner_text()

                # Best-effort screenshot of the rendered carrier page. A failure
                # here must not prevent returning the tracking details.
                screenshot_line = ""
                try:
                    png_bytes = await page.screenshot(full_page=True)
                    screenshot_url = _upload_screenshot(png_bytes, tracking_number)
                    if screenshot_url:
                        # Markdown image syntax so the Streamlit chat renders it inline.
                        screenshot_line = f"\nPage screenshot: ![carrier tracking page]({screenshot_url})"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Screenshot capture failed: %s", exc, exc_info=True)

                return (
                    f"Tracking ID: {tracking_number}\n"
                    f"Carrier: {carrier}\n"
                    f"Status: {status}\n"
                    f"Current location: {location}\n"
                    f"Estimated delivery: {estimate}\n"
                    f"Details: {detail}"
                    f"{screenshot_line}"
                )
            except Exception:
                # The page uses the same result container for an unknown number.
                error = page.locator(".error")
                if await error.count():
                    return await error.inner_text()
                raise
            finally:
                await browser.close()


@tool
def check_carrier_tracking(tracking_number: str) -> str:
    """
    Check a shipment on the ShopSmart carrier tracking website using Browser.

    Use this when a customer asks for the latest carrier status or delivery
    estimate and an order's tracking number is available. The tracking portal
    is external to the ShopSmart API, so use this tool rather than guessing.
    """
    if not cfg.carrier_tracking_url:
        return "Carrier tracking is not configured."
    if not isinstance(tracking_number, str) or not tracking_number.strip():
        return "A tracking number is required."

    try:
        return asyncio.run(_lookup_tracking(tracking_number.strip()))
    except Exception as exc:  # noqa: BLE001
        logger.error("Carrier Browser lookup failed: %s", exc, exc_info=True)
        return "Carrier tracking is temporarily unavailable."
