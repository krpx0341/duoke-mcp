#!/usr/bin/env python3
import os
import re
import shutil
import time

from pathlib import Path
from typing import Any


from mcp.server.fastmcp import FastMCP
from playwright.sync_api import BrowserContext, Page, sync_playwright

DUOKE_URL = "https://ai.duoke.com/"
PROFILE_DIR = Path(__file__).parent / "browser-profile"
CHROMIUM = os.environ.get("DUOKE_CHROMIUM") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")

if not CHROMIUM:
    raise RuntimeError("Chromium not found. Install Chromium or set DUOKE_CHROMIUM to its executable path.")

mcp = FastMCP("duoke", instructions="Duoke inbox, order, and customer tools. Use list_inbox before opening a conversation. Sending requires confirm=true.")
_pw = None
_context: BrowserContext | None = None


def _context_get() -> BrowserContext:
    global _pw, _context
    if _context:
        return _context
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    _pw = sync_playwright().start()
    _context = _pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        executable_path=CHROMIUM,
        headless=True,
        args=["--profile-directory=Profile 1", "--disable-blink-features=AutomationControlled"],
    )
    return _context


def _page() -> Page:
    context = _context_get()
    page = context.pages[0] if context.pages else context.new_page()
    if "ai.duoke.com" not in page.url:
        page.goto(DUOKE_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(2_000)
    return page


def _visible_text(page: Page) -> str:
    return page.locator("body").inner_text().strip()


def _ensure_login(page: Page) -> None:
    if "/login" in page.url or page.get_by_text(re.compile(r"^(Login|登录)$", re.I)).count():
        raise RuntimeError(
            "Duoke session not logged in. Run ./login.sh (or the login script in this folder), finish login, close browser, then retry."
        )


def _click_first(page: Page, labels: list[str]) -> bool:
    for label in labels:
        locator = page.get_by_text(re.compile(re.escape(label), re.I)).first
        try:
            if locator.is_visible(timeout=500):
                locator.click()
                page.wait_for_timeout(1_500)
                return True
        except Exception:
            pass
    return False


def _items(page: Page, selectors: list[str], limit: int) -> list[dict[str, str]]:
    for selector in selectors:
        rows = page.locator(selector)
        if rows.count() < 1:
            continue
        result = []
        for i in range(min(rows.count(), limit)):
            row = rows.nth(i)
            try:
                text = row.inner_text().strip()
                if text:
                    result.append({"index": str(i), "text": text[:1500]})
            except Exception:
                pass
        if result:
            return result
    return []


@mcp.tool()
def status() -> dict[str, Any]:
    """Check Duoke session and current page without changing data."""
    page = _page()
    return {
        "url": page.url,
        "title": page.title(),
        "logged_in": "/login" not in page.url and not bool(page.get_by_text(re.compile(r"^(Login|登录)$", re.I)).count()),
        "profile": str(PROFILE_DIR),
    }


@mcp.tool()
def list_inbox(limit: int = 20, unread_only: bool = False) -> dict[str, Any]:
    """List recent Duoke conversations. Returns compact visible rows; no messages are sent."""
    page = _page()
    _ensure_login(page)
    _click_first(page, ["消息", "会话", "Inbox", "Messages", "Chats"])
    selectors = [
        "[class*='conversation'] [class*='item']",
        "[class*='session'] [class*='item']",
        "[class*='chat-list'] > *",
        "[class*='contact-list'] > *",
        "[role='listitem']",
    ]
    rows = _items(page, selectors, max(1, min(limit, 100)))
    if unread_only:
        rows = [r for r in rows if re.search(r"unread|未读|\b[1-9]\d*\b", r["text"], re.I)]
    return {"count": len(rows), "conversations": rows}


@mcp.tool()
def read_conversation(index: int = 0, limit: int = 30) -> dict[str, Any]:
    """Open one conversation by index from list_inbox and return recent visible messages."""
    page = _page()
    _ensure_login(page)
    inbox = list_inbox(limit=max(index + 1, 20))
    if index < 0 or index >= inbox["count"]:
        raise ValueError(f"conversation index {index} out of range")
    selectors = [
        "[class*='conversation'] [class*='item']",
        "[class*='session'] [class*='item']",
        "[class*='chat-list'] > *",
        "[class*='contact-list'] > *",
        "[role='listitem']",
    ]
    for selector in selectors:
        rows = page.locator(selector)
        if rows.count() > index:
            rows.nth(index).click()
            page.wait_for_timeout(1_200)
            break
    messages = _items(
        page,
        ["[class*='message-item']", "[class*='message']", "[class*='bubble']", "[role='log'] > *"],
        max(1, min(limit, 100)),
    )
    return {"conversation": inbox["conversations"][index], "count": len(messages), "messages": messages[-limit:]}


@mcp.tool()
def send_reply(index: int, text: str, confirm: bool = False) -> dict[str, Any]:
    """Send reply to conversation index. Requires confirm=true to prevent accidental sends."""
    if not confirm:
        return {"sent": False, "confirmation_required": True, "index": index, "preview": text}
    if not text.strip() or len(text) > 4000:
        raise ValueError("text must contain 1..4000 characters")
    page = _page()
    _ensure_login(page)
    read_conversation(index=index, limit=1)
    editors = [
        "textarea",
        "[contenteditable='true']",
        "[class*='editor'] textarea",
        "[class*='input'] textarea",
    ]
    editor = None
    for selector in editors:
        candidate = page.locator(selector).last
        try:
            if candidate.is_visible(timeout=500):
                editor = candidate
                break
        except Exception:
            pass
    if editor is None:
        raise RuntimeError("Duoke reply editor not found")
    editor.fill(text)
    if not _click_first(page, ["发送", "Send", "Reply"]):
        editor.press("Enter")
    page.wait_for_timeout(1_000)
    return {"sent": True, "index": index, "text": text}


@mcp.tool()
def search_orders(query: str, limit: int = 20) -> dict[str, Any]:
    """Search visible Duoke orders by order ID, buyer, store, phone, or product text."""
    if not query.strip():
        raise ValueError("query is required")
    page = _page()
    _ensure_login(page)
    _click_first(page, ["订单", "Orders"])
    inputs = page.locator("input")
    for i in range(inputs.count()):
        field = inputs.nth(i)
        hint = " ".join(filter(None, [field.get_attribute("placeholder"), field.get_attribute("aria-label")]))
        if re.search(r"search|order|buyer|搜索|订单|买家", hint, re.I):
            field.fill(query)
            field.press("Enter")
            page.wait_for_timeout(1_500)
            break
    rows = _items(page, ["[class*='order'] [class*='item']", "tbody tr", "[role='row']"], max(1, min(limit, 100)))
    return {"query": query, "count": len(rows), "orders": rows}


@mcp.tool()
def search_customers(query: str, limit: int = 20) -> dict[str, Any]:
    """Search visible Duoke customers by name, account, email, phone, or platform ID."""
    if not query.strip():
        raise ValueError("query is required")
    page = _page()
    _ensure_login(page)
    _click_first(page, ["客户", "买家", "Customers", "Buyers"])
    inputs = page.locator("input")
    for i in range(inputs.count()):
        field = inputs.nth(i)
        hint = " ".join(filter(None, [field.get_attribute("placeholder"), field.get_attribute("aria-label")]))
        if re.search(r"search|customer|buyer|搜索|客户|买家", hint, re.I):
            field.fill(query)
            field.press("Enter")
            page.wait_for_timeout(1_500)
            break
    rows = _items(page, ["[class*='customer'] [class*='item']", "[class*='buyer'] [class*='item']", "tbody tr", "[role='row']"], max(1, min(limit, 100)))
    return {"query": query, "count": len(rows), "customers": rows}


if __name__ == "__main__":
    mcp.run(transport="stdio")
