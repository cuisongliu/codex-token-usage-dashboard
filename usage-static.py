#!/usr/bin/env python3
"""Collect Codex token usage into static dashboard data files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


DEFAULT_BASE_URL = "https://your-sub2api.example.com"
DEFAULT_API_PREFIX = "/v1"
DEFAULT_PROVIDER = "OpenAI"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_DAYS = 31
DEFAULT_REFRESH_MINUTES = 5
CONFIG_PATH = pathlib.Path("config.yaml")


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str
    provider: str
    base_url: str
    api_prefix: str
    auth_token: str
    timezone: str
    days: int
    refresh_minutes: int
    data_json: pathlib.Path
    data_js: pathlib.Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static Codex token usage data from config.yaml.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="collect",
        choices=("sync-config", "collect", "watch", "print-config"),
        help="sync-config initializes config.yaml from ~/.codex; collect writes data files.",
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PATH),
        help="Path to config.yaml. Default: ./config.yaml",
    )
    parser.add_argument(
        "--codex-home",
        default=os.environ.get("CODEX_HOME", str(pathlib.Path.home() / ".codex")),
        help="Codex home used only when initializing config.yaml.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite config.yaml when running sync-config.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run watch as a single collect cycle.",
    )
    return parser.parse_args()


def today_in_timezone(timezone: str) -> str:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo(timezone)).date().isoformat()
    except Exception:
        return dt.datetime.now().date().isoformat()


def add_days(date_text: str, days: int) -> str:
    value = dt.date.fromisoformat(date_text)
    return (value + dt.timedelta(days=days)).isoformat()


def date_range(start_date: str, end_date: str) -> list[str]:
    start = dt.date.fromisoformat(start_date)
    end = dt.date.fromisoformat(end_date)
    days: list[str] = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)
    return days


def to_number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def to_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def trim_slashes(value: str) -> str:
    return str(value or "").rstrip("/")


def normalize_prefix(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return "/" + text.strip("/")


def yaml_quote(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_yaml(path: pathlib.Path, values: dict[str, Any]) -> None:
    lines = [
        "# Generated from ~/.codex. Keep this file private.",
        "# The static HTML never reads this file directly.",
    ]
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int):
            rendered = str(value)
        else:
            rendered = yaml_quote(str(value))
        lines.append(f"{key}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def unquote_yaml(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1]
    return text.replace('\\"', '"').replace("\\\\", "\\")


def parse_simple_yaml(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{line_number} is not a key: value line.")
        key, value = line.split(":", 1)
        values[key.strip()] = unquote_yaml(value)
    return values


def strip_quotes(value: str) -> str:
    text = value.strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    return text


def parse_codex_toml_fallback(path: pathlib.Path) -> dict[str, Any]:
    data: dict[str, Any] = {"model_providers": {}}
    current_provider = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section.startswith("model_providers."):
                current_provider = strip_quotes(section.removeprefix("model_providers."))
                data["model_providers"].setdefault(current_provider, {})
            else:
                current_provider = ""
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = strip_quotes(raw_value.strip())
        if current_provider:
            data["model_providers"][current_provider][key] = value
        else:
            data[key] = value
    return data


def read_codex_config(codex_home: pathlib.Path) -> tuple[str, dict[str, Any]]:
    config_path = codex_home / "config.toml"
    if tomllib:
        with config_path.open("rb") as file:
            data = tomllib.load(file)
    else:
        data = parse_codex_toml_fallback(config_path)
    provider = str(data.get("model_provider") or DEFAULT_PROVIDER)
    providers = data.get("model_providers") or {}
    provider_config = providers.get(provider) or {}
    return provider, provider_config


def read_codex_token(codex_home: pathlib.Path) -> str:
    auth_path = codex_home / "auth.json"
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    token = data.get("OPENAI_API_KEY") or data.get("openai_api_key") or data.get("api_key")
    if not token:
        raise ValueError(f"No OPENAI_API_KEY found in {auth_path}.")
    return str(token)


def sync_config(config_path: pathlib.Path, codex_home: pathlib.Path, force: bool) -> None:
    if config_path.exists() and not force:
        print(f"{config_path} already exists; not overwritten. Use --force to resync.")
        return

    provider, provider_config = read_codex_config(codex_home)
    token = read_codex_token(codex_home)
    values = {
        "mode": "codex",
        "provider": provider,
        "base_url": provider_config.get("base_url") or DEFAULT_BASE_URL,
        "api_prefix": DEFAULT_API_PREFIX,
        "auth_token": token,
        "timezone": DEFAULT_TIMEZONE,
        "days": DEFAULT_DAYS,
        "refresh_minutes": DEFAULT_REFRESH_MINUTES,
        "data_json": "usage-data.json",
        "data_js": "usage-data.js",
    }
    write_yaml(config_path, values)
    print(f"Wrote {config_path} from {codex_home}.")
    print("Keep config.yaml private; it contains an API key.")


def ensure_config(config_path: pathlib.Path, codex_home: pathlib.Path) -> None:
    if not config_path.exists():
        sync_config(config_path, codex_home, force=False)


def load_runtime_config(config_path: pathlib.Path, codex_home: pathlib.Path) -> RuntimeConfig:
    ensure_config(config_path, codex_home)
    raw = parse_simple_yaml(config_path)
    base_dir = config_path.resolve().parent
    return RuntimeConfig(
        mode=raw.get("mode", "codex"),
        provider=raw.get("provider", DEFAULT_PROVIDER),
        base_url=trim_slashes(raw.get("base_url", DEFAULT_BASE_URL)),
        api_prefix=normalize_prefix(raw.get("api_prefix", DEFAULT_API_PREFIX)),
        auth_token=raw.get("auth_token", ""),
        timezone=raw.get("timezone", DEFAULT_TIMEZONE),
        days=to_int(raw.get("days"), DEFAULT_DAYS),
        refresh_minutes=to_int(raw.get("refresh_minutes"), DEFAULT_REFRESH_MINUTES),
        data_json=base_dir / raw.get("data_json", "usage-data.json"),
        data_js=base_dir / raw.get("data_js", "usage-data.js"),
    )


def request_json(config: RuntimeConfig, path: str, params: dict[str, Any] | None = None) -> Any:
    if not config.auth_token:
        raise ValueError("auth_token is empty in config.yaml.")
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
    url = f"{config.base_url}{config.api_prefix}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {config.auth_token}",
            "Content-Type": "application/json",
            "X-Timezone": config.timezone,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{error.code} {body}") from error
    return json.loads(body) if body else {}


def empty_day(date_text: str) -> dict[str, Any]:
    return {
        "date": date_text,
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
        "actual_cost_usd": 0,
        "standard_cost_usd": 0,
        "records": 0,
        "source": "empty",
    }


def normalize_usage_day(item: dict[str, Any], fallback_date: str = "") -> dict[str, Any]:
    row = empty_day(str(item.get("date") or item.get("day") or fallback_date))
    row.update(
        {
            "requests": to_number(item.get("requests") or item.get("total_requests")),
            "input_tokens": to_number(item.get("input_tokens") or item.get("total_input_tokens")),
            "output_tokens": to_number(item.get("output_tokens") or item.get("total_output_tokens")),
            "cache_creation_tokens": to_number(
                item.get("cache_creation_tokens")
                or item.get("cache_write_tokens")
                or item.get("cacheCreateTokens")
                or item.get("total_cache_creation_tokens")
            ),
            "cache_read_tokens": to_number(
                item.get("cache_read_tokens") or item.get("total_cache_read_tokens")
            ),
            "actual_cost_usd": to_number(item.get("actual_cost") or item.get("total_actual_cost")),
            "standard_cost_usd": to_number(item.get("cost") or item.get("total_cost")),
            "records": to_number(item.get("records")),
            "source": "codex",
        }
    )
    row["total_tokens"] = to_number(item.get("total_tokens")) or (
        row["input_tokens"]
        + row["output_tokens"]
        + row["cache_creation_tokens"]
        + row["cache_read_tokens"]
    )
    return row


def sum_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
        "actual_cost_usd": 0,
        "standard_cost_usd": 0,
        "records": 0,
    }
    for row in rows:
        for key in total:
            total[key] += to_number(row.get(key))
    return total


def start_of_week(date_text: str) -> str:
    value = dt.date.fromisoformat(date_text)
    return (value - dt.timedelta(days=value.weekday())).isoformat()


def start_of_month(date_text: str) -> str:
    value = dt.date.fromisoformat(date_text)
    return value.replace(day=1).isoformat()


def period_report(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"name": name, "start_date": "", "end_date": "", "days": [], "totals": sum_rows([])}
    return {
        "name": name,
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "days": rows,
        "totals": sum_rows(rows),
    }


def build_report(config: RuntimeConfig) -> dict[str, Any]:
    data = request_json(config, "/usage")
    today = today_in_timezone(config.timezone)
    start_date = add_days(today, -(max(config.days, 1) - 1))
    dates = date_range(start_date, today)
    by_date: dict[str, dict[str, Any]] = {}

    for item in data.get("daily_usage") or []:
        if isinstance(item, dict):
            row = normalize_usage_day(item)
            if row["date"]:
                by_date[row["date"]] = row

    if isinstance(data.get("usage"), dict) and isinstance(data["usage"].get("today"), dict):
        by_date[today] = normalize_usage_day(data["usage"]["today"], fallback_date=today)

    rows = [by_date.get(date_text, empty_day(date_text)) for date_text in dates]
    week_start = start_of_week(today)
    month_start = start_of_month(today)
    week_rows = [row for row in rows if week_start <= row["date"] <= today]
    month_rows = [row for row in rows if month_start <= row["date"] <= today]
    today_rows = [row for row in rows if row["date"] == today]

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_version": 1,
        "mode": config.mode,
        "provider": config.provider,
        "base_url": config.base_url,
        "api_prefix": config.api_prefix,
        "timezone": config.timezone,
        "refresh_minutes": config.refresh_minutes,
        "start_date": start_date,
        "end_date": today,
        "days": rows,
        "totals": sum_rows(rows),
        "periods": {
            "day": period_report("今日", today_rows),
            "week": period_report("本周", week_rows),
            "month": period_report("本月", month_rows),
            "range": period_report("近期开销", rows),
        },
        "raw_usage_status": data.get("status"),
        "expires_at": data.get("expires_at"),
        "days_until_expiry": data.get("days_until_expiry"),
        "model_stats": data.get("model_stats") if isinstance(data.get("model_stats"), list) else [],
    }


def write_report(config: RuntimeConfig, report: dict[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    config.data_json.write_text(text + "\n", encoding="utf-8")
    config.data_js.write_text(
        "window.DAILY_TOKEN_USAGE_DATA = "
        + text
        + ";\n"
        + 'window.DAILY_TOKEN_USAGE_DATA_SOURCE = "generated";\n'
        + "window.__USAGE_DATA__ = window.DAILY_TOKEN_USAGE_DATA;\n",
        encoding="utf-8",
    )


def collect(config_path: pathlib.Path, codex_home: pathlib.Path) -> RuntimeConfig:
    config = load_runtime_config(config_path, codex_home)
    report = build_report(config)
    write_report(config, report)
    totals = report["periods"]["day"]["totals"]
    print(
        "Collected "
        f"{int(totals['total_tokens']):,} tokens for today; "
        f"wrote {config.data_json.name} and {config.data_js.name}."
    )
    return config


def print_safe_config(config: RuntimeConfig) -> None:
    safe = {
        "mode": config.mode,
        "provider": config.provider,
        "base_url": config.base_url,
        "api_prefix": config.api_prefix,
        "auth_token": "***" if config.auth_token else "",
        "timezone": config.timezone,
        "days": config.days,
        "refresh_minutes": config.refresh_minutes,
        "data_json": str(config.data_json),
        "data_js": str(config.data_js),
    }
    print(json.dumps(safe, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    config_path = pathlib.Path(args.config)
    codex_home = pathlib.Path(args.codex_home).expanduser()

    if args.command == "sync-config":
        sync_config(config_path, codex_home, force=args.force)
        return 0

    if args.command == "print-config":
        print_safe_config(load_runtime_config(config_path, codex_home))
        return 0

    if args.command == "collect":
        collect(config_path, codex_home)
        return 0

    if args.command == "watch":
        while True:
            config = collect(config_path, codex_home)
            if args.once:
                return 0
            time.sleep(max(config.refresh_minutes, 1) * 60)

    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
