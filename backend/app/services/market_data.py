from __future__ import annotations

import copy
import calendar
import importlib.util
import json
import re
import threading
import time
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any, Callable

from app.config import settings


_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()

FUTURES_SYMBOLS: dict[str, tuple[str, ...]] = {
    "precious_metals": ("AU0", "AG0", "CU0", "AL0"),
    "cotton": ("CF0",),
    "agriculture": ("C0", "M0", "SR0"),
}

ETF_SYMBOLS = ("510300", "159915", "512100")

TUSHARE_FUTURES: dict[str, tuple[str, ...]] = {
    "precious_metals": ("AU", "AG", "CU", "AL"),
    "cotton": ("CF",),
    "agriculture": ("C", "M", "SR"),
}

TUSHARE_EXCHANGES: dict[str, tuple[str, ...]] = {
    "precious_metals": ("SHFE",),
    "cotton": ("CZCE",),
    "agriculture": ("DCE", "CZCE"),
}


def provider_health() -> dict[str, Any]:
    return {
        "default": settings.market_data_source,
        "akshare": {
            "installed": importlib.util.find_spec("akshare") is not None,
            "configured": True,
            "requires_credentials": False,
        },
        "tushare": {
            "installed": importlib.util.find_spec("tushare") is not None,
            "configured": bool(settings.tushare_token),
            "requires_credentials": True,
        },
    }


def _target_date(value: str) -> date_type:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date_type.today()


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    text = str(value).strip()
    compact_quarter = re.fullmatch(r"((?:19|20)\d{2})\s*[Qq](\d)", text)
    if compact_quarter:
        return f"{compact_quarter.group(1)}-{int(compact_quarter.group(2)) * 3:02d}-01"
    chinese_month = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", text)
    if chinese_month:
        return f"{chinese_month.group(1)}-{int(chinese_month.group(2)):02d}-01"
    chinese_quarter = re.search(r"(20\d{2}).*?(\d)(?:\s*-\s*(\d))?\s*季度", text)
    if chinese_quarter:
        quarter = int(chinese_quarter.group(3) or chinese_quarter.group(2))
        return f"{chinese_quarter.group(1)}-{quarter * 3:02d}-01"
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(digits) == 6:
        return f"{digits[:4]}-{digits[4:6]}-01"
    return text[:10]


def _next_month(value: date_type, day: int) -> date_type:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return date_type(year, month, min(day, calendar.monthrange(year, month)[1]))


def _availability_date(period: date_type, endpoint: str) -> date_type:
    endpoint = endpoint.lower()
    if "cpi" in endpoint or "ppi" in endpoint:
        return _next_month(period, 10)
    if "pmi" in endpoint:
        return _next_month(period, 1)
    if "gdp" in endpoint:
        return _next_month(period, 20)
    return period


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and value != value:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _records_from_frame(frame: Any, target: date_type, endpoint: str, limit: int = 3) -> list[dict[str, Any]]:
    if frame is None or not hasattr(frame, "to_dict") or getattr(frame, "empty", False):
        return []
    rows = frame.to_dict(orient="records")
    normalized: list[tuple[str, dict[str, Any]]] = []
    date_keys = (
        "date",
        "trade_date",
        "month",
        "quarter",
        "DATE",
        "TRADE_DATE",
        "MONTH",
        "QUARTER",
        "日期",
        "月份",
        "季度",
        "报告期",
        "统计时间",
    )
    for row in rows:
        clean = {str(key): _json_value(value) for key, value in row.items()}
        row_date = ""
        for key in date_keys:
            if key in row and row.get(key) is not None:
                row_date = _date_text(row.get(key))
                clean[str(key)] = row_date
                break
        if row_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row_date):
            try:
                period = datetime.strptime(row_date, "%Y-%m-%d").date()
                if _availability_date(period, endpoint) > target:
                    continue
            except ValueError:
                pass
        normalized.append((row_date, clean))
    normalized.sort(key=lambda item: item[0])
    return [record for _, record in normalized[-limit:]]


def _snapshot(
    provider: str,
    endpoint: str,
    instrument: str,
    frame: Any,
    target: date_type,
    category: str,
) -> dict[str, Any] | None:
    records = _records_from_frame(frame, target, endpoint)
    if not records:
        return None
    return {
        "provider": provider,
        "endpoint": endpoint,
        "instrument": instrument,
        "category": category,
        "records": records,
    }


def _run_calls(calls: list[tuple[str, str, str, Callable[[], Any]]], provider: str, target: date_type) -> tuple[list[dict[str, Any]], list[str]]:
    snapshots: list[dict[str, Any]] = []
    errors: list[str] = []
    for endpoint, instrument, category, callback in calls:
        try:
            item = _snapshot(provider, endpoint, instrument, callback(), target, category)
            if item:
                snapshots.append(item)
        except Exception as exc:  # noqa: BLE001 - one public endpoint must not stop the report.
            message = str(exc)
            if settings.tushare_token:
                message = message.replace(settings.tushare_token, "***")
            errors.append(f"{endpoint}({instrument}): {message[:500]}")
    return snapshots, errors


def _akshare_snapshots(domain_key: str, target: date_type) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if importlib.util.find_spec("akshare") is None:
        return [], {"status": "not_installed", "calls": 0, "errors": ["akshare is not installed"]}
    import akshare as ak

    calls: list[tuple[str, str, str, Callable[[], Any]]] = []
    if domain_key in FUTURES_SYMBOLS:
        for symbol in FUTURES_SYMBOLS[domain_key]:
            calls.append(("futures_zh_daily_sina", symbol, "market", lambda symbol=symbol: ak.futures_zh_daily_sina(symbol=symbol)))
    elif domain_key == "etf":
        start = (target - timedelta(days=settings.market_data_lookback_days)).strftime("%Y%m%d")
        end = target.strftime("%Y%m%d")
        for symbol in ETF_SYMBOLS:
            calls.append(
                (
                    "fund_etf_hist_em",
                    symbol,
                    "market",
                    lambda symbol=symbol: ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start, end_date=end, adjust=""),
                )
            )
    else:
        macro_calls = (
            ("macro_china_cpi", "中国CPI", "macro", ak.macro_china_cpi),
            ("macro_china_ppi", "中国PPI", "macro", ak.macro_china_ppi),
            ("macro_china_pmi", "中国PMI", "macro", ak.macro_china_pmi),
            ("macro_china_gdp", "中国GDP", "macro", ak.macro_china_gdp),
        )
        calls.extend(macro_calls)

    snapshots, errors = _run_calls(calls, "AkShare", target)
    return snapshots, {
        "status": "found" if snapshots else ("error" if errors else "no_data"),
        "calls": len(calls),
        "found": len(snapshots),
        "errors": errors[:6],
    }


def _tushare_snapshots(domain_key: str, target: date_type) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if importlib.util.find_spec("tushare") is None:
        return [], {"status": "not_installed", "calls": 0, "errors": ["tushare is not installed"]}
    if not settings.tushare_token:
        return [], {"status": "not_configured", "calls": 0, "errors": ["TUSHARE_TOKEN is not configured"]}

    import tushare as ts

    pro = ts.pro_api(settings.tushare_token)
    calls: list[tuple[str, str, str, Callable[[], Any]]] = []
    start = (target - timedelta(days=settings.market_data_lookback_days)).strftime("%Y%m%d")
    end = target.strftime("%Y%m%d")
    if domain_key in TUSHARE_FUTURES:
        prefixes = TUSHARE_FUTURES[domain_key]
        for exchange in TUSHARE_EXCHANGES[domain_key]:
            def fetch_futures(exchange: str = exchange) -> Any:
                frame = pro.query("fut_daily", exchange=exchange, start_date=start, end_date=end)
                if frame is None or getattr(frame, "empty", False) or "ts_code" not in frame.columns:
                    return frame
                pattern = "^(?:" + "|".join(re.escape(prefix) for prefix in prefixes) + ")"
                return frame[frame["ts_code"].astype(str).str.match(pattern, case=False, na=False)]

            calls.append(("fut_daily", exchange, "market", fetch_futures))
    elif domain_key == "etf":
        for ts_code in ("510300.SH", "159915.SZ", "512100.SH"):
            calls.append(
                (
                    "fund_daily",
                    ts_code,
                    "market",
                    lambda ts_code=ts_code: pro.query("fund_daily", ts_code=ts_code, start_date=start, end_date=end),
                )
            )
    else:
        for endpoint, instrument in (("cn_cpi", "中国CPI"), ("cn_ppi", "中国PPI"), ("cn_pmi", "中国PMI"), ("cn_gdp", "中国GDP")):
            calls.append((endpoint, instrument, "macro", lambda endpoint=endpoint: pro.query(endpoint)))

    snapshots, errors = _run_calls(calls, "Tushare", target)
    return snapshots, {
        "status": "found" if snapshots else ("error" if errors else "no_data"),
        "calls": len(calls),
        "found": len(snapshots),
        "errors": errors[:6],
    }


def _snapshot_text(snapshot: dict[str, Any], query_date: str) -> str:
    payload = json.dumps(snapshot["records"], ensure_ascii=False, separators=(",", ":"))
    return (
        f"{snapshot['provider']} 可核验数据；接口={snapshot['endpoint']}；"
        f"标的={snapshot['instrument']}；查询截止={query_date}；记录={payload[:1800]}"
    )


def _snapshots_for_node(node: dict[str, Any], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requirements = " ".join(str(item) for item in node.get("materials", [])).lower()
    wants_macro = any(token in requirements for token in ("macro", "growth", "rates_fx", "policy", "宏观", "利率", "政策"))
    wants_market = any(token in requirements for token in ("market", "price", "inventory", "supply", "demand", "价格", "库存", "供给", "需求"))
    chosen: list[dict[str, Any]] = []
    if wants_market:
        chosen.extend(item for item in snapshots if item["category"] == "market")
    if wants_macro:
        chosen.extend(item for item in snapshots if item["category"] == "macro")
    if not chosen:
        chosen = snapshots
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in chosen:
        key = (item["provider"], item["endpoint"], item["instrument"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:8]


def _build_result(
    *,
    source: str,
    query_date: str,
    order: list[str],
    frontend_node_by_id: dict[str, dict[str, Any]],
    snapshots: list[dict[str, Any]],
    providers: dict[str, Any],
) -> dict[str, Any]:
    by_node: dict[str, list[dict[str, Any]]] = {}
    all_bindings: list[dict[str, Any]] = []
    for node_id in order:
        node = frontend_node_by_id.get(node_id)
        if not node:
            continue
        bindings = []
        for snapshot in _snapshots_for_node(node, snapshots):
            binding = {
                "node_id": node_id,
                "state_label": node.get("label", ""),
                "required_material": ", ".join(node.get("materials", [])) or "state evidence",
                "date": query_date,
                "provider": snapshot["provider"],
                "endpoint": snapshot["endpoint"],
                "instrument": snapshot["instrument"],
                "status": "found",
                "error": "",
                "records": snapshot["records"],
                "raw_text": _snapshot_text(snapshot, query_date),
            }
            bindings.append(binding)
            all_bindings.append(binding)
        by_node[node_id] = bindings

    found = len(all_bindings)
    errors = [error for provider in providers.values() for error in provider.get("errors", [])]
    if found:
        status = "found"
    elif any(provider.get("status") == "not_configured" for provider in providers.values()) and source == "tushare":
        status = "not_configured"
    elif errors:
        status = "error"
    else:
        status = "no_data"
    used = [name for name, detail in providers.items() if detail.get("found")]
    return {
        "enabled": source != "none",
        "requested": True,
        "used": bool(found),
        "mode": "market-data",
        "source": source,
        "status": status,
        "providers_requested": list(providers),
        "providers_used": used,
        "providers": providers,
        "summary": {
            "total": found,
            "found": found,
            "status_counts": {"found": found} if found else {status: 1},
        },
        "error": errors[0] if errors and not found else "",
        "query_date": query_date,
        "bindings_by_node": by_node,
    }


def retrieve_market_materials(
    *,
    source: str,
    domain_key: str,
    query_date: str,
    order: list[str],
    frontend_node_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = source if source in {"auto", "akshare", "tushare"} else "auto"
    key = (selected, domain_key, query_date)
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached[0] <= settings.market_data_cache_seconds:
            result = copy.deepcopy(cached[1])
            result["cache_hit"] = True
            return result

    target = _target_date(query_date)
    snapshots: list[dict[str, Any]] = []
    providers: dict[str, Any] = {}
    if selected in {"auto", "akshare"}:
        items, detail = _akshare_snapshots(domain_key, target)
        snapshots.extend(items)
        providers["AkShare"] = detail
    if selected in {"auto", "tushare"}:
        items, detail = _tushare_snapshots(domain_key, target)
        snapshots.extend(items)
        providers["Tushare"] = detail

    result = _build_result(
        source=selected,
        query_date=query_date,
        order=order,
        frontend_node_by_id=frontend_node_by_id,
        snapshots=snapshots,
        providers=providers,
    )
    result["cache_hit"] = False
    with _CACHE_LOCK:
        _CACHE[key] = (now, copy.deepcopy(result))
    return result
