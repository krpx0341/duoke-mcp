# Duoke MCP

Local MCP server for [Duoke](https://ai.duoke.com/). Gives Grok/GrokBot compact domain tools for reading customer conversations, replying with explicit confirmation, and searching orders or customers.

This integration drives Duoke through an isolated Chromium profile. Each operator signs in with their own Duoke account. Browser sessions are never shared or committed.

## Tools

| Tool | Mode | Purpose |
| --- | --- | --- |
| `status` | Read-only | Check browser session and login state |
| `list_inbox(limit=20, unread_only=false)` | Read-only | List recent conversations |
| `read_conversation(index=0, limit=30)` | Read-only | Read recent messages from one conversation |
| `send_reply(index, text, confirm=false)` | Write | Preview by default; sends only when `confirm=true` |
| `search_orders(query, limit=20)` | Read-only | Search orders by visible ID, buyer, store, phone, or product text |
| `search_customers(query, limit=20)` | Read-only | Search customers by visible name, account, email, phone, or platform ID |

## Requirements

- Linux
- Python 3.11+
- Chromium or Google Chrome
- Grok CLI/GrokBot with local stdio MCP support
- Duoke account

If Chromium is not on `PATH`, set `DUOKE_CHROMIUM` to its executable path.

## Install

```bash
git clone https://github.com/krpx0341/duoke-mcp.git
cd duoke-mcp
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
chmod +x duoke-mcp login.sh server.py
```

No browser download is required. Server uses installed Chromium or Chrome.

## Authenticate

```bash
./login.sh
```

Sign in to Duoke in opened browser, confirm inbox is accessible, then close browser. Login state stays in local `browser-profile/` directory.

Never copy or commit `browser-profile/`. Every operator must authenticate their own account.

## Register with Grok/GrokBot

```bash
grok mcp add duoke -- "$(pwd)/duoke-mcp"
grok mcp doctor duoke --json
```

Expected doctor result:

- server started
- handshake OK
- 6 tools discovered

Restart Grok/GrokBot if it does not hot-reload MCP configuration.

## Agent operating guide

Agents should follow this sequence:

1. Call `status` before first domain operation.
2. Call `list_inbox` before `read_conversation` or `send_reply`.
3. Treat returned conversation `index` as temporary UI position, not durable ID.
4. Call `send_reply` first with `confirm=false` to produce preview.
5. Ask human to approve exact conversation and message.
6. Call `send_reply` again with identical arguments and `confirm=true`.
7. Never claim reply succeeded unless tool returns `sent: true`.
8. Keep `limit` small unless broader retrieval is necessary.

Example agent requests:

```text
Use Duoke. Check status, then list 10 unread conversations.

Read conversation index 0 and summarize customer intent. Do not reply.

Preview this reply for conversation index 0: "Pesanan sedang kami cek."
Do not send until I approve.

Search orders for "ORDER-12345" and return only matching rows.
```

## Manual MCP configuration

Equivalent entry in `~/.grok/config.toml`:

```toml
[mcp_servers.duoke]
command = "/absolute/path/to/duoke-mcp/duoke-mcp"
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Then run:

```bash
grok mcp doctor duoke --json
```

## Troubleshooting

### `Duoke session not logged in`

Run `./login.sh`, finish login, close browser, then retry.

### Browser profile is locked

Close browser opened by `login.sh` before calling MCP tools. Only one Chromium process can own profile at a time.

### Chromium not found

```bash
export DUOKE_CHROMIUM=/path/to/chromium
```

Keep variable available to MCP process. For Grok config:

```toml
[mcp_servers.duoke]
command = "/absolute/path/to/duoke-mcp/duoke-mcp"
env = { DUOKE_CHROMIUM = "/path/to/chromium" }
```

### Tools are discovered but return no rows

Duoke changes UI selectors occasionally. Verify account can access target page in `./login.sh`, then open an issue with:

- Duoke language
- failing tool name
- visible page section
- sanitized error text

Do not attach cookies, profile files, customer conversations, or credentials.

## Security

- `browser-profile/` contains authenticated session material and is gitignored.
- `send_reply` requires `confirm=true`.
- Package exposes domain tools, not generic browser click or arbitrary JavaScript execution.
- Each installation belongs to one operator and one Duoke session.
- Do not expose this stdio server as shared network service.

## Verification

```bash
python -m py_compile server.py
bash -n login.sh duoke-mcp
python scripts/check_tools.py
grok mcp doctor duoke --json
```

Protocol discovery does not prove live Duoke behavior. Complete verification requires authenticated `status`, one real read call, and an approved low-risk reply test.

## Current limitations

- Browser automation depends on Duoke UI labels/selectors.
- Conversation indices can change when inbox order changes.
- Designed for one operator, one process, one Duoke browser profile.
- Linux launcher only.
