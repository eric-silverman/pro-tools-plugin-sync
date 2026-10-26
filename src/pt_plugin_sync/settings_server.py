from __future__ import annotations

import html
from dataclasses import replace
from email.parser import BytesParser
from email.policy import default
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from typing import Callable

try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11
    tomllib = None

from .config import (
    Config,
    DEFAULT_AUTO_UPDATE_DOWNLOAD,
    DEFAULT_DEBOUNCE_SECONDS,
    DEFAULT_HASH_BINARIES,
    DEFAULT_REPORTS_BACKEND,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    validate_config,
    write_config,
)
from .dropbox_auth import DROPBOX_OAUTH_SCOPES


class SettingsServer:
    def __init__(self, config: Config, on_save: Callable[[Config], None]) -> None:
        self._config = config
        self._on_save = on_save
        self._server: TCPServer | None = None
        self._thread: threading.Thread | None = None
        self._url: str | None = None

    @property
    def url(self) -> str | None:
        return self._url

    def is_running(self) -> bool:
        return self._server is not None

    def start(self) -> str:
        if self._server is not None and self._url is not None:
            return self._url

        handler = self._make_handler()
        self._server = TCPServer(("127.0.0.1", 0), handler)
        host, port = self._server.server_address
        self._url = f"http://{host}:{port}/"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._url

    def dropbox_auth_url(self) -> str:
        base = self.start()
        return f"{base}dropbox-auth-start"

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._url = None

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args) -> None:  # noqa: N802
                return

            def do_GET(self) -> None:  # noqa: N802
                if self.path in ("/", "/index.html"):
                    notice = _pop_notice(server)
                    body = _render_form(server._config, notice=notice)
                    self._send_html(body)
                    return
                if self.path == "/dropbox-auth-start":
                    app_key = server._config.dropbox_app_key or ""
                    app_secret = server._config.dropbox_app_secret or ""
                    if not app_key or not app_secret:
                        self._send_html(
                            _render_error("Enter the Dropbox app key and secret first.")
                        )
                        return
                    try:
                        authorize_url = _dropbox_authorize_url(app_key, app_secret)
                    except Exception as exc:
                        self._send_html(_render_error(str(exc)))
                        return
                    self._send_html(
                        _render_dropbox_auth(app_key, app_secret, authorize_url)
                    )
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/save":
                    values = _read_form_values(self)
                    try:
                        updated = _config_from_form(values, server._config)
                    except ValueError as exc:
                        self._send_html(_render_error(str(exc)))
                        return
                    error = _finalize_save(updated, server)
                    if error:
                        self._send_html(_render_error(error))
                        return
                    _set_notice(server, "Settings saved.")
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if self.path == "/dropbox-auth":
                    values = _read_form_values(self)
                    app_key = _get_text(values, "dropbox_app_key")
                    app_secret = _get_text(values, "dropbox_app_secret")
                    if not app_key or not app_secret:
                        self._send_html(
                            _render_error("Dropbox app key and secret are required.")
                        )
                        return
                    try:
                        authorize_url = _dropbox_authorize_url(app_key, app_secret)
                    except Exception as exc:
                        self._send_html(_render_error(str(exc)))
                        return
                    self._send_html(
                        _render_dropbox_auth(app_key, app_secret, authorize_url)
                    )
                    return
                if self.path == "/dropbox-finish":
                    values = _read_form_values(self)
                    app_key = _get_text(values, "dropbox_app_key")
                    app_secret = _get_text(values, "dropbox_app_secret")
                    auth_code = _get_text(values, "auth_code")
                    if not app_key or not app_secret:
                        self._send_html(
                            _render_error("Dropbox app key and secret are required.")
                        )
                        return
                    if not auth_code:
                        self._send_html(_render_error("Authorization code is required."))
                        return
                    try:
                        refresh_token = _dropbox_finish_auth(
                            app_key, app_secret, auth_code
                        )
                    except Exception as exc:
                        self._send_html(_render_error(str(exc)))
                        return
                    server._config = replace(
                        server._config,
                        dropbox_app_key=app_key,
                        dropbox_app_secret=app_secret,
                        dropbox_refresh_token=refresh_token,
                    )
                    _set_notice(
                        server,
                        "Dropbox refresh token captured. Click Save Settings to persist.",
                    )
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                if self.path == "/import":
                    try:
                        updated = _config_from_upload(self, server._config)
                    except ValueError as exc:
                        self._send_html(_render_error(str(exc)))
                        return
                    error = _finalize_save(updated, server)
                    if error:
                        self._send_html(_render_error(error))
                        return
                    _set_notice(server, "Settings imported.")
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def _send_html(self, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


def _render_form(config: Config, *, notice: str | None) -> str:
    def esc(value: str) -> str:
        return html.escape(value, quote=True)

    backend = (config.reports_backend or "local").strip().lower()
    backend_local = "selected" if backend == "local" else ""
    backend_dropbox = "selected" if backend == "dropbox" else ""
    hash_checked = "checked" if config.hash_binaries else ""
    auto_update_checked = "checked" if config.auto_update_download else ""
    dropbox_path = config.dropbox_reports_path or "/Pro Tools Plugin Reports"
    notice_html = (
        f'<div class="banner">{esc(notice)}</div>' if notice else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pro Tools Plugin Sync Settings</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #0f3a3f;
      --panel: #fdf7eb;
      --ink: #1a1a18;
      --muted: #6e6a61;
      --accent: #e3c07a;
      --accent-dark: #caa45c;
      --accent-soft: #f2e4c6;
      --line: #efe2c8;
      --shadow: rgba(6, 23, 24, 0.22);
    }}
    body {{
      margin: 0;
      font-family: "SF Pro Text", "Helvetica Neue", "Avenir Next", sans-serif;
      background:
        radial-gradient(circle at top left, #16464c 0%, #0f3a3f 50%, #0b2f33 100%),
        linear-gradient(120deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0));
      color: var(--ink);
      min-height: 100vh;
    }}
    .backdrop {{
      position: fixed;
      inset: 0;
      background:
        radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.18), transparent 55%),
        radial-gradient(circle at 90% 10%, rgba(227, 192, 122, 0.25), transparent 50%);
      pointer-events: none;
    }}
    .wrap {{
      max-width: 820px;
      margin: 48px auto;
      padding: 36px 40px 28px;
      background: var(--panel);
      border-radius: 20px;
      box-shadow: 0 24px 60px var(--shadow);
      border: 1px solid #efe2c8;
      position: relative;
      overflow: hidden;
      animation: lift 0.6s ease-out;
    }}
    .wrap::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255, 242, 220, 0.5), transparent 45%);
      pointer-events: none;
    }}
    h1 {{
      margin: 0 0 6px;
      font-family: "Avenir Next", "SF Pro Display", "Helvetica Neue", sans-serif;
      font-size: 28px;
      letter-spacing: 0.4px;
    }}
    h2 {{
      font-family: "Avenir Next", "SF Pro Display", "Helvetica Neue", sans-serif;
      font-size: 18px;
      margin: 0 0 12px;
    }}
    p {{
      margin: 0 0 22px;
      color: var(--muted);
    }}
    .section {{
      margin-top: 26px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      animation: fade 0.5s ease-out both;
    }}
    .section:nth-of-type(1) {{ animation-delay: 0.05s; }}
    .section:nth-of-type(2) {{ animation-delay: 0.1s; }}
    .section:nth-of-type(3) {{ animation-delay: 0.15s; }}
    .section:nth-of-type(4) {{ animation-delay: 0.2s; }}
    label {{
      display: block;
      margin: 12px 0 6px;
      font-weight: 600;
      color: #2a251f;
    }}
    input, select {{
      width: 100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid #dbcaa9;
      font-size: 14px;
      background: #fffaf1;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    input:focus, select:focus {{
      outline: none;
      border-color: var(--accent-dark);
      box-shadow: 0 0 0 3px rgba(227, 192, 122, 0.25);
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    .checkbox {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 10px;
    }}
    .checkbox input {{
      width: auto;
    }}
    .callout {{
      margin-top: 12px;
      padding: 14px 16px;
      border-radius: 12px;
      background: #f7ead1;
      border: 1px solid #e8d2a7;
      color: #5a452a;
      font-size: 13px;
    }}
    .callout ol {{
      margin: 10px 0 0 18px;
      padding: 0;
    }}
    .callout a {{
      color: #8b5a1a;
      text-decoration: none;
      font-weight: 600;
    }}
    .callout a:hover {{
      text-decoration: underline;
    }}
    .banner {{
      margin: 0 0 18px;
      padding: 10px 14px;
      border-radius: 12px;
      background: #e5f0ee;
      border: 1px solid #c2d9d5;
      color: #1b4f52;
      font-weight: 600;
    }}
    .import-block {{
      margin-top: 18px;
      padding: 16px;
      border-radius: 14px;
      background: #f6edd8;
      border: 1px dashed #d9c49d;
    }}
    .import-block button {{
      margin-top: 12px;
    }}
    .actions {{
      margin-top: 30px;
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      position: relative;
      z-index: 1;
    }}
    button {{
      border: none;
      padding: 11px 20px;
      border-radius: 12px;
      font-size: 14px;
      cursor: pointer;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    button:active {{
      transform: translateY(1px);
    }}
    .primary {{
      background: var(--accent);
      color: #3b2a12;
      box-shadow: 0 10px 20px rgba(227, 192, 122, 0.35);
    }}
    .ghost {{
      background: transparent;
      border: 1px solid #d9c49d;
      color: var(--ink);
    }}
    .note {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 8px;
    }}
    .hidden {{
      display: none;
    }}
    @keyframes lift {{
      from {{ transform: translateY(10px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
    @keyframes fade {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 720px) {{
      .row {{
        grid-template-columns: 1fr;
      }}
      .wrap {{
        margin: 28px 16px;
        padding: 26px;
      }}
    }}
  </style>
</head>
<body>
  <div class="backdrop"></div>
  <div class="wrap">
    <form method="post" action="/save">
      {notice_html}
      <h1>Pro Tools Plugin Sync</h1>
      <p>Configure how scans run and where reports are stored.</p>

    <div class="section">
      <h2>General</h2>
      <label for="machine_name">Machine name</label>
      <input id="machine_name" name="machine_name" value="{esc(config.machine_name)}">

      <label for="plugins_path">Plugins folder</label>
      <input id="plugins_path" name="plugins_path" value="{esc(config.plugins_path)}">

      <div class="row">
        <div>
          <label for="scan_interval_seconds">Scan interval (seconds)</label>
          <input id="scan_interval_seconds" name="scan_interval_seconds" value="{config.scan_interval_seconds}">
        </div>
        <div>
          <label for="debounce_seconds">Debounce (seconds)</label>
          <input id="debounce_seconds" name="debounce_seconds" value="{config.debounce_seconds}">
        </div>
      </div>
    </div>

    <div class="section">
      <h2>Storage</h2>
      <label for="reports_backend">Reports backend</label>
      <select id="reports_backend" name="reports_backend">
        <option value="local" {backend_local}>Local</option>
        <option value="dropbox" {backend_dropbox}>Dropbox</option>
      </select>

      <label for="reports_path">Reports folder</label>
      <input id="reports_path" name="reports_path" value="{esc(config.reports_path)}">
    </div>

    <div class="section" id="dropbox_section">
      <h2>Dropbox</h2>
      <div class="callout">
        Create a Dropbox app:
        <ol>
          <li>Visit <a href="https://www.dropbox.com/developers/apps" target="_blank" rel="noopener">Dropbox App Console</a>.</li>
          <li>Choose "Scoped access" and "App folder", then name the app.</li>
          <li>Open the app, add scopes for read/write, then use "Authorize Dropbox..." below.</li>
        </ol>
        Helpful docs: <a href="https://dropbox.tech/developers/generate-an-access-token-for-your-own-account" target="_blank" rel="noopener">Generate a token</a>
      </div>

      <label for="dropbox_reports_path">Dropbox reports path</label>
      <input id="dropbox_reports_path" name="dropbox_reports_path" value="{esc(dropbox_path)}">

      <label for="dropbox_app_key">Dropbox app key</label>
      <input id="dropbox_app_key" name="dropbox_app_key" value="{esc(config.dropbox_app_key or '')}">

      <label for="dropbox_app_secret">Dropbox app secret</label>
      <input id="dropbox_app_secret" name="dropbox_app_secret" value="{esc(config.dropbox_app_secret or '')}">

      <label for="dropbox_refresh_token">Dropbox refresh token</label>
      <input id="dropbox_refresh_token" name="dropbox_refresh_token" value="{esc(config.dropbox_refresh_token or '')}">
      <div class="note">Needed only when using Dropbox as the backend.</div>

      <button class="ghost" type="button" onclick="startDropboxAuth()">Authorize Dropbox...</button>
      <div class="note">Runs the OAuth flow without the CLI and fills the refresh token.</div>
    </div>

      <div class="section">
        <h2>Advanced</h2>
      <div class="row">
        <div>
          <label for="prune_days">Prune reports (days)</label>
          <input id="prune_days" name="prune_days" value="{config.prune_days}">
        </div>
      </div>
      <div class="checkbox">
        <input id="hash_binaries" name="hash_binaries" type="checkbox" {hash_checked}>
        <label for="hash_binaries">Hash binaries</label>
      </div>
        <div class="checkbox">
          <input id="auto_update_download" name="auto_update_download" type="checkbox" {auto_update_checked}>
          <label for="auto_update_download">Download updates automatically</label>
        </div>
      </div>

      <div class="actions">
        <button class="ghost" type="button" onclick="window.close()">Close</button>
        <button class="primary" type="submit">Save Settings</button>
      </div>
    </form>

    <form class="import-block" method="post" action="/import" enctype="multipart/form-data">
      <strong>Import config file</strong>
      <p class="note">Upload an existing config.toml to replace these values.</p>
      <input type="file" name="config_file" accept=".toml,text/plain">
      <button class="ghost" type="submit">Import Config</button>
    </form>
  </div>

  <script>
    const backend = document.getElementById('reports_backend');
    const dropbox = document.getElementById('dropbox_section');
    function toggleDropbox() {{
      dropbox.classList.toggle('hidden', backend.value !== 'dropbox');
    }}
    backend.addEventListener('change', toggleDropbox);
    toggleDropbox();

    function startDropboxAuth() {{
      const appKey = document.getElementById('dropbox_app_key').value.trim();
      const appSecret = document.getElementById('dropbox_app_secret').value.trim();
      if (!appKey || !appSecret) {{
        window.alert('Enter the Dropbox app key and secret first.');
        return;
      }}
      const form = document.createElement('form');
      form.method = 'post';
      form.action = '/dropbox-auth';
      const keyField = document.createElement('input');
      keyField.type = 'hidden';
      keyField.name = 'dropbox_app_key';
      keyField.value = appKey;
      const secretField = document.createElement('input');
      secretField.type = 'hidden';
      secretField.name = 'dropbox_app_secret';
      secretField.value = appSecret;
      form.appendChild(keyField);
      form.appendChild(secretField);
      document.body.appendChild(form);
      form.submit();
    }}
  </script>
</body>
</html>
"""


def _config_from_form(values: dict[str, list[str]], current: Config) -> Config:
    def get_text(key: str, default: str = "") -> str:
        return (values.get(key, [default])[0] or "").strip()

    def get_int(key: str, default: int) -> int:
        raw = get_text(key, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be a number.") from exc

    backend = get_text("reports_backend", current.reports_backend).lower()
    if backend not in {"local", "dropbox"}:
        raise ValueError("reports_backend must be local or dropbox.")

    dropbox_reports_path = get_text(
        "dropbox_reports_path", current.dropbox_reports_path or "/Pro Tools Plugin Reports"
    )
    dropbox_app_key = get_text("dropbox_app_key", current.dropbox_app_key or "")
    dropbox_app_secret = get_text("dropbox_app_secret", current.dropbox_app_secret or "")
    dropbox_refresh_token = get_text(
        "dropbox_refresh_token", current.dropbox_refresh_token or ""
    )

    return Config(
        machine_name=get_text("machine_name", current.machine_name),
        plugins_path=get_text("plugins_path", current.plugins_path),
        reports_path=get_text("reports_path", current.reports_path),
        reports_backend=backend,
        dropbox_app_key=dropbox_app_key or None,
        dropbox_app_secret=dropbox_app_secret or None,
        dropbox_refresh_token=dropbox_refresh_token or None,
        dropbox_reports_path=dropbox_reports_path or None,
        scan_interval_seconds=get_int(
            "scan_interval_seconds", current.scan_interval_seconds
        ),
        debounce_seconds=get_int("debounce_seconds", current.debounce_seconds),
        hash_binaries="hash_binaries" in values,
        prune_days=get_int("prune_days", current.prune_days),
        auto_update_download="auto_update_download" in values,
    )


def _config_from_upload(handler: BaseHTTPRequestHandler, current: Config) -> Config:
    if tomllib is None:
        raise ValueError("TOML parsing requires Python 3.11+.")
    content_type = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        raise ValueError("Empty upload.")
    data = handler.rfile.read(length)
    file_bytes = _extract_multipart_file(data, content_type, "config_file")
    try:
        payload = tomllib.loads(file_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to parse TOML: {exc}") from exc
    return _config_from_toml(payload, current)


def _config_from_toml(payload: dict, current: Config) -> Config:
    def text(key: str, default: str) -> str:
        value = payload.get(key, default)
        return str(value or default)

    def none_if_blank(value: object | None) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None

    def integer(key: str, default: int) -> int:
        value = payload.get(key, default)
        return int(value)

    backend = str(payload.get("reports_backend", DEFAULT_REPORTS_BACKEND)).strip().lower()
    return Config(
        machine_name=text("machine_name", current.machine_name),
        plugins_path=text("plugins_path", current.plugins_path),
        reports_path=text("reports_path", current.reports_path),
        reports_backend=backend,
        dropbox_app_key=none_if_blank(payload.get("dropbox_app_key")),
        dropbox_app_secret=none_if_blank(payload.get("dropbox_app_secret")),
        dropbox_refresh_token=none_if_blank(payload.get("dropbox_refresh_token")),
        dropbox_reports_path=none_if_blank(payload.get("dropbox_reports_path")),
        scan_interval_seconds=integer("scan_interval_seconds", DEFAULT_SCAN_INTERVAL_SECONDS),
        debounce_seconds=integer("debounce_seconds", DEFAULT_DEBOUNCE_SECONDS),
        hash_binaries=bool(payload.get("hash_binaries", DEFAULT_HASH_BINARIES)),
        prune_days=integer("prune_days", 0),
        auto_update_download=bool(
            payload.get("auto_update_download", DEFAULT_AUTO_UPDATE_DOWNLOAD)
        ),
    )


def _finalize_save(updated: Config, server: SettingsServer) -> str | None:
    if updated.reports_backend == "local":
        try:
            reports_dir = updated.expanded_reports_path()
            reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"reports_path error: {exc}"
    validation = validate_config(updated)
    if not validation.ok:
        return "\n".join(validation.errors)
    server._config = updated
    write_config(updated)
    server._on_save(updated)
    return None


def _extract_multipart_file(body: bytes, content_type: str, field_name: str) -> bytes:
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Expected multipart/form-data.")
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            raise ValueError("Uploaded file is empty.")
        return payload
    raise ValueError("No config_file provided.")


def _read_form_values(handler: BaseHTTPRequestHandler) -> dict[str, list[str]]:
    length = int(handler.headers.get("Content-Length", "0"))
    data = handler.rfile.read(length).decode("utf-8")
    return urllib.parse.parse_qs(data)


def _get_text(values: dict[str, list[str]], key: str, default: str = "") -> str:
    return (values.get(key, [default])[0] or "").strip()


def _format_scopes(scopes: list[str]) -> str:
    return ", ".join(scopes)


def _dropbox_authorize_url(app_key: str, app_secret: str) -> str:
    try:
        from dropbox import DropboxOAuth2FlowNoRedirect
    except Exception as exc:
        raise RuntimeError("Dropbox SDK not available.") from exc
    flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type="offline",
        scope=DROPBOX_OAUTH_SCOPES,
    )
    return flow.start()


def _dropbox_finish_auth(app_key: str, app_secret: str, auth_code: str) -> str:
    try:
        from dropbox import DropboxOAuth2FlowNoRedirect
    except Exception as exc:
        raise RuntimeError("Dropbox SDK not available.") from exc
    flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type="offline",
        scope=DROPBOX_OAUTH_SCOPES,
    )
    oauth_result = flow.finish(auth_code)
    if not oauth_result.refresh_token:
        raise RuntimeError(
            "Dropbox did not return a refresh token. Ensure short-lived tokens are enabled."
        )
    return oauth_result.refresh_token


def _render_dropbox_auth(app_key: str, app_secret: str, authorize_url: str) -> str:
    safe_url = html.escape(authorize_url, quote=True)
    scopes = html.escape(_format_scopes(DROPBOX_OAUTH_SCOPES), quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dropbox Authorization</title>
  <style>
    body {{
      margin: 0;
      padding: 32px;
      font-family: "SF Pro Text", "Helvetica Neue", "Avenir Next", sans-serif;
      background: #f4f0e6;
      color: #1a1a18;
    }}
    .card {{
      max-width: 760px;
      margin: 0 auto;
      padding: 28px;
      border-radius: 16px;
      background: #ffffff;
      border: 1px solid #e0d6c1;
      box-shadow: 0 18px 36px rgba(24, 24, 24, 0.18);
    }}
    h1 {{
      margin-top: 0;
      font-size: 24px;
    }}
    a {{
      color: #8b5a1a;
      font-weight: 600;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    label {{
      display: block;
      margin-top: 16px;
      font-weight: 600;
    }}
    input {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid #dbcaa9;
      margin-top: 6px;
    }}
    button {{
      margin-top: 18px;
      border: none;
      padding: 10px 18px;
      border-radius: 10px;
      background: #e3c07a;
      cursor: pointer;
      font-weight: 600;
    }}
    .note {{
      margin-top: 10px;
      font-size: 12px;
      color: #6e6a61;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Dropbox authorization</h1>
    <ol>
      <li>Open this URL in a browser and approve access:</li>
    </ol>
    <p><a href="{safe_url}" target="_blank" rel="noopener">{safe_url}</a></p>
    <p class="note">Scopes requested: {scopes}</p>
    <form method="post" action="/dropbox-finish">
      <input type="hidden" name="dropbox_app_key" value="{html.escape(app_key, quote=True)}">
      <input type="hidden" name="dropbox_app_secret" value="{html.escape(app_secret, quote=True)}">
      <label for="auth_code">Authorization code</label>
      <input id="auth_code" name="auth_code" autocomplete="off">
      <button type="submit">Save refresh token</button>
    </form>
    <p class="note"><a href="/">Back to settings</a></p>
  </div>
</body>
</html>
"""


def _render_error(message: str) -> str:
    safe = html.escape(message, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Settings Error</title>
  <style>
    body {{ font-family: "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif; padding: 40px; }}
    .card {{ max-width: 640px; margin: 0 auto; padding: 24px; border-radius: 12px; background: #fff3f0; }}
    h1 {{ margin-top: 0; }}
    pre {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Could not save settings</h1>
    <pre>{safe}</pre>
    <p><a href="/">Go back</a></p>
  </div>
</body>
</html>
"""


def _set_notice(server: SettingsServer, message: str) -> None:
    server._notice = message


def _pop_notice(server: SettingsServer) -> str | None:
    notice = getattr(server, "_notice", None)
    server._notice = None
    return notice
