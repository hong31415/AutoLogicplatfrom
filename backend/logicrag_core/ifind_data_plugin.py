"""
LogicRAG iFinD data plugin.

This module turns a query-specific subtree produced by query_processing.py into
state-bound market data files:

1. Parse the reference date from the user query.
2. Read required_materials from query_subtree.json.
3. Resolve CODES from domain_dictionary.csv.
4. Query iFinD historical quotations through THS_HQ.
5. Save both a flat CSV and node/material-level JSON bindings for generation.

Credentials are intentionally read from environment variables or CLI arguments.
Do not hard-code account information in this file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pandas as pd
except ModuleNotFoundError:  # Optional in the portable offline demo.
    pd = None


DEFAULT_TEMPLATE = "logicrag_outputs/query_subtree.json"
DEFAULT_OUTPUT_DIR = "logicrag_outputs/retrieved_materials"
DEFAULT_DICTIONARY = "domain_dictionary.csv"

DEFAULT_FUTURES_INDICATORS = [
    "preSettlement",
    "settlement",
    "change_settlement",
    "change",
    "changeRatio",
    "chg_settlement",
    "volume",
    "openInterest",
]

DEFAULT_STOCK_INDICATORS = [
    "open",
    "high",
    "low",
    "close",
    "change",
    "changeRatio",
    "volume",
]

CONTRACT_SUFFIXES = [
    "连续",
]

MONTH_TO_NUMBER = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

INDICATOR_KEYWORDS = {
    "preSettlement": ["previous settlement", "pre settlement", "pre_settle", "昨结", "前结算"],
    "settlement": ["settlement", "settle", "closing price", "close price", "price", "收盘", "结算", "价格"],
    "change_settlement": ["settlement change", "settle change", "结算变动"],
    "change": ["change", "涨跌", "变动", "涨跌额"],
    "changeRatio": ["change ratio", "pct", "percentage", "percent", "%", "涨跌幅", "环比", "同比"],
    "chg_settlement": ["settlement change ratio", "结算涨跌幅"],
    "volume": ["volume", "trading volume", "成交量"],
    "openInterest": ["open interest", "持仓", "持仓量"],
}

def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    text = str(text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = text.replace("（", "(").replace("）", ")")
    return text


def unique_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def split_aliases(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in re.split(r"[|;,，、]", text) if item.strip()]


def dictionary_terms(name: str, aliases: Any = "") -> List[str]:
    terms = [name, *split_aliases(aliases)]
    for term in list(terms):
        for suffix in CONTRACT_SUFFIXES:
            if term.endswith(suffix):
                terms.append(term[: -len(suffix)])
    return unique_keep_order(normalize_text(term) for term in terms if len(normalize_text(term)) >= 2)


def parse_query_date(query: str) -> str:
    """Extract one reference date from a user query as YYYY-MM-DD."""
    text = str(query)

    patterns = [
        (r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", "%Y-%m-%d"),
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "%Y-%m-%d"),
    ]
    for pattern, _ in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = map(int, match.groups())
            return datetime(year, month, day).strftime("%Y-%m-%d")

    month_names = (
        "january|jan\\.?|february|feb\\.?|march|mar\\.?|april|apr\\.?|may|"
        "june|jun\\.?|july|jul\\.?|august|aug\\.?|september|sep\\.?|sept\\.?|"
        "october|oct\\.?|november|nov\\.?|december|dec\\.?"
    )
    month_first = re.search(
        rf"\b({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b",
        text,
        flags=re.IGNORECASE,
    )
    if month_first:
        month, day, year = month_first.groups()
        month_num = MONTH_TO_NUMBER[month.rstrip(".").lower()]
        return datetime(int(year), month_num, int(day)).strftime("%Y-%m-%d")

    day_first = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})[,]?\s+(\d{{4}})\b",
        text,
        flags=re.IGNORECASE,
    )
    if day_first:
        day, month, year = day_first.groups()
        month_num = MONTH_TO_NUMBER[month.rstrip(".").lower()]
        return datetime(int(year), month_num, int(day)).strftime("%Y-%m-%d")

    raise ValueError(f"Cannot parse query date from query: {query}")


class FuturesDomainDictionary:
    """Resolve futures names to iFinD CODES using domain_dictionary.csv."""

    def __init__(self, csv_path: str | Path = DEFAULT_DICTIONARY) -> None:
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Cannot find domain dictionary: {self.csv_path}")
        self.df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        required_cols = {"CODE", "Name"}
        if not required_cols.issubset(self.df.columns):
            raise ValueError(f"domain_dictionary.csv must contain columns {required_cols}.")
        self.df["CODE"] = self.df["CODE"].astype(str).str.strip()
        self.df["Name"] = self.df["Name"].astype(str).str.strip()
        if "Aliases" not in self.df.columns:
            self.df["Aliases"] = ""
        self.df["Aliases"] = self.df["Aliases"].fillna("").astype(str)
        self.df["_match_terms"] = self.df.apply(
            lambda row: dictionary_terms(str(row["Name"]), row.get("Aliases", "")),
            axis=1,
        )
        self.df["_norm_name"] = self.df["Name"].apply(normalize_text)

    def resolve(self, query_name: str) -> str:
        query = normalize_text(query_name)
        exact = self.df[self.df["_norm_name"] == query]
        if not exact.empty:
            return str(exact.iloc[0]["CODE"])

        contains_name = self.df[self.df["_norm_name"].apply(lambda name: bool(name and name in query))]
        if not contains_name.empty:
            contains_name = contains_name.assign(_len=contains_name["_norm_name"].str.len())
            contains_name = contains_name.sort_values("_len", ascending=False)
            return str(contains_name.iloc[0]["CODE"])

        name_contains = self.df[self.df["_norm_name"].apply(lambda name: bool(query and query in name))]
        if not name_contains.empty:
            ranked = self._rank_candidates(name_contains)
            return str(ranked.iloc[0]["CODE"])

        raise KeyError(f"Cannot resolve futures code from query: {query_name}")

    def scan_codes(self, text: str) -> List[str]:
        norm_text = normalize_text(text)
        matched = self.df[
            self.df["_match_terms"].apply(lambda terms: any(term and term in norm_text for term in terms))
        ]
        if matched.empty:
            return []
        matched = matched.assign(
            _len=matched["_match_terms"].apply(
                lambda terms: max((len(term) for term in terms if term in norm_text), default=0)
            )
        ).sort_values("_len", ascending=False)
        return unique_keep_order(matched["CODE"].tolist())

    def _rank_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        def score(name: str) -> int:
            if "主连" in name:
                return 100
            if "连续" in name:
                return 95
            if "连一" in name:
                return 80
            if "加权" in name:
                return 70
            if re.search(r"\d{4}", name):
                return 50
            return 10

        ranked = candidates.copy()
        ranked["_rank"] = ranked["Name"].apply(score)
        return ranked.sort_values("_rank", ascending=False)


@dataclass
class RetrievalSpec:
    node_id: str
    state_label: str
    required_material: str
    codes: List[str]
    indicators: List[str]
    date: str
    asset_type: str = "future"
    resolver_notes: List[str] = field(default_factory=list)


class RequiredMaterialResolver:
    """Map required_materials to CODES and INDICATORS."""

    def __init__(self, dictionary_path: str | Path = DEFAULT_DICTIONARY) -> None:
        self.dictionary = FuturesDomainDictionary(dictionary_path)

    def resolve_codes(self, text: str, asset_name: Optional[str] = None) -> Tuple[List[str], List[str]]:
        notes: List[str] = []
        search_text = f"{asset_name or ''}\n{text}"

        dictionary_codes = self.dictionary.scan_codes(search_text)
        if dictionary_codes:
            notes.append("resolved by domain_dictionary.csv")
            return dictionary_codes, notes

        return [], notes

    def resolve_indicators(self, text: str, default: Sequence[str] = DEFAULT_FUTURES_INDICATORS) -> List[str]:
        norm = normalize_text(text)
        indicators: List[str] = []
        for indicator, keywords in INDICATOR_KEYWORDS.items():
            if any(normalize_text(keyword) in norm for keyword in keywords):
                indicators.append(indicator)

        if not indicators:
            return list(default)

        # For price-change requirements, keep enough context to compute and
        # verbalize both absolute and percentage changes.
        if any(ind in indicators for ind in ["settlement", "change", "changeRatio", "change_settlement"]):
            indicators.extend(["preSettlement", "settlement", "change", "changeRatio"])
        return unique_keep_order(indicators)

    def build_specs(
        self,
        query_subtree: Dict[str, Any],
        query: str,
        date: str,
        asset_name: Optional[str] = None,
    ) -> List[RetrievalSpec]:
        nodes = query_subtree.get("node_template", {}).get("nodes", [])
        specs: List[RetrievalSpec] = []
        for node in nodes:
            node_id = str(node.get("node_id", ""))
            label = str(node.get("template_description", ""))
            desc = str(node.get("content_guideline", ""))
            materials = [str(item).strip() for item in as_list(node.get("required_materials")) if str(item).strip()]
            for material in materials:
                material_context = f"{query}\n{material}"
                full_context = f"{query}\n{label}\n{desc}\n{material}"
                codes, notes = self.resolve_codes(material_context, asset_name=asset_name)
                if not codes:
                    codes, notes = self.resolve_codes(full_context, asset_name=asset_name)
                indicators = self.resolve_indicators(full_context)
                specs.append(
                    RetrievalSpec(
                        node_id=node_id,
                        state_label=label,
                        required_material=material,
                        codes=codes,
                        indicators=indicators,
                        date=date,
                        asset_type="future" if codes else "unresolved",
                        resolver_notes=notes,
                    )
                )
        return specs


class IFINDDataClient:
    """Thin wrapper around iFinDPy with fixed error handling."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None) -> None:
        self.username = username or os.environ.get("IFIND_USERNAME")
        self.password = password or os.environ.get("IFIND_PASSWORD")
        self._logged_in = False

    def _ifind(self):
        try:
            import iFinDPy
        except ImportError as exc:
            raise RuntimeError("iFinDPy is not installed or not configured on this machine.") from exc
        return iFinDPy

    def login(self) -> None:
        if self._logged_in:
            return
        if not self.username or not self.password:
            raise RuntimeError("Missing iFinD credentials. Set IFIND_USERNAME and IFIND_PASSWORD or pass CLI args.")
        api = self._ifind()
        code = api.THS_iFinDLogin(self.username, self.password)
        if code not in (0, -201):
            raise RuntimeError(f"iFinD login failed with code {code}.")
        self._logged_in = True

    def logout(self) -> None:
        if not self._logged_in:
            return
        api = self._ifind()
        api.THS_iFinDLogout()
        self._logged_in = False

    def cmd_history_quotation(
        self,
        codes: Sequence[str],
        indicators: Sequence[str],
        date: str,
    ) -> pd.DataFrame:
        """Query historical quotation data through iFinD THS_HQ."""
        if not codes:
            raise ValueError("codes cannot be empty for cmd_history_quotation.")
        if not indicators:
            raise ValueError("indicators cannot be empty for cmd_history_quotation.")
        self.login()
        api = self._ifind()
        result = api.THS_HQ(
            ",".join(codes),
            ",".join(indicators),
            "Fill:Blank",
            date,
            date,
            "format:dataframe",
        )
        self._raise_if_error(result, "THS_HQ")
        df = self._to_dataframe(result)
        if df.empty:
            return df
        df.insert(0, "query_date", date)
        df.insert(1, "query_codes", ",".join(codes))
        df.insert(2, "query_indicators", ",".join(indicators))
        return df

    @staticmethod
    def _raise_if_error(result: Any, context: str) -> None:
        errorcode = getattr(result, "errorcode", 0)
        if errorcode != 0:
            errmsg = getattr(result, "errmsg", "")
            raise RuntimeError(f"{context} failed: errorcode={errorcode}, errmsg={errmsg}")

    @staticmethod
    def _to_dataframe(result: Any) -> pd.DataFrame:
        data = getattr(result, "data", result)
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict):
            return pd.DataFrame([data])
        return pd.DataFrame()


def records_to_raw_text(records: Sequence[Dict[str, Any]]) -> str:
    if not records:
        return ""
    parts = []
    for record in records:
        code = record.get("thscode") or record.get("THSCODE") or record.get("code") or record.get("query_codes", "")
        values = []
        for key, value in record.items():
            if key in {"node_id", "state_label", "required_material", "resolver_notes"}:
                continue
            if pd.notna(value):
                values.append(f"{key}={value}")
        parts.append(f"{code}: " + ", ".join(values))
    return "\n".join(parts)


def dataframe_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def fetch_data_for_specs(
    specs: Sequence[RetrievalSpec],
    client: IFINDDataClient,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    flat_records: List[Dict[str, Any]] = []
    bindings: List[Dict[str, Any]] = []

    for spec in specs:
        status = "planned"
        error = ""
        records: List[Dict[str, Any]] = []

        if not spec.codes:
            status = "unresolved"
            error = "No futures CODES resolved from query_subtree required_materials."
        elif not dry_run:
            try:
                df = client.cmd_history_quotation(spec.codes, spec.indicators, spec.date)
                records = dataframe_records(df)
                status = "found" if records else "empty"
            except Exception as exc:
                status = "error"
                error = str(exc)

        annotated_records = []
        for record in records:
            annotated = dict(record)
            annotated["node_id"] = spec.node_id
            annotated["state_label"] = spec.state_label
            annotated["required_material"] = spec.required_material
            annotated["resolver_notes"] = "; ".join(spec.resolver_notes)
            annotated_records.append(annotated)
        flat_records.extend(annotated_records)

        bindings.append(
            {
                "node_id": spec.node_id,
                "state_label": spec.state_label,
                "required_material": spec.required_material,
                "date": spec.date,
                "asset_type": spec.asset_type,
                "codes": spec.codes,
                "indicators": spec.indicators,
                "resolver_notes": spec.resolver_notes,
                "status": status,
                "error": error,
                "records": records,
                "raw_text": records_to_raw_text(records),
            }
        )

    return flat_records, bindings


def save_node_material_files(
    bindings: Sequence[Dict[str, Any]],
    output_dir: str | Path,
    template_id: str,
    query: str,
    query_date: str,
) -> Dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    by_node: Dict[str, List[Dict[str, Any]]] = {}
    for binding in bindings:
        by_node.setdefault(str(binding["node_id"]), []).append(binding)

    node_files: Dict[str, str] = {}
    for node_id, node_bindings in by_node.items():
        extraction_results = {}
        missing = []
        found = 0
        for binding in node_bindings:
            material = binding["required_material"]
            is_found = binding["status"] == "found"
            if is_found:
                found += 1
            else:
                missing.append(material)
            extraction_results[material] = {
                "material_name": material,
                "found": is_found,
                "raw_text": binding.get("raw_text", ""),
                "query": {
                    "date": binding["date"],
                    "codes": binding["codes"],
                    "indicators": binding["indicators"],
                },
                "records": binding.get("records", []),
                "status": binding["status"],
                "error": binding.get("error", ""),
            }

        payload = {
            "node_id": node_id,
            "template_id": template_id,
            "query": query,
            "query_date": query_date,
            "extraction_results": extraction_results,
            "summary": {
                "total": len(node_bindings),
                "found": found,
                "missing": missing,
            },
        }
        safe_node_id = node_id.replace(".", "_")
        file_path = output_path / f"materials_{safe_node_id}.json"
        save_json(payload, file_path)
        node_files[node_id] = str(file_path)

    save_json(
        {
            "template_id": template_id,
            "query": query,
            "query_date": query_date,
            "node_files": node_files,
        },
        output_path / "materials_index.json",
    )
    return node_files


def run_data_plugin(args: argparse.Namespace) -> Dict[str, Any]:
    if pd is None:
        raise RuntimeError("pandas is required when iFinD data retrieval is enabled.")
    query_subtree = load_json(args.query_subtree)
    query = str(args.query or "").strip()
    if not query:
        raise ValueError("A user query is required. Pass --query explicitly.")
    query_date = args.date or parse_query_date(query)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resolver = RequiredMaterialResolver(args.dictionary)
    specs = resolver.build_specs(
        query_subtree=query_subtree,
        query=query,
        date=query_date,
        asset_name=args.asset_name or None,
    )

    client = IFINDDataClient(username=args.username, password=args.password)
    flat_records, bindings = fetch_data_for_specs(specs, client=client, dry_run=args.dry_run)
    if not args.dry_run:
        client.logout()

    flat_csv_path = output_dir / "retrieved_data.csv"
    if flat_records:
        pd.DataFrame(flat_records).to_csv(flat_csv_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(
            [
                {
                    "node_id": spec.node_id,
                    "required_material": spec.required_material,
                    "query_date": spec.date,
                    "query_codes": ",".join(spec.codes),
                    "query_indicators": ",".join(spec.indicators),
                    "status": next((b["status"] for b in bindings if b["node_id"] == spec.node_id and b["required_material"] == spec.required_material), "planned"),
                }
                for spec in specs
            ]
        ).to_csv(flat_csv_path, index=False, encoding="utf-8-sig")

    template_id = query_subtree.get("template_id", "query_subtree")
    node_files = save_node_material_files(bindings, output_dir, template_id, query, query_date)

    result = {
        "template_id": template_id,
        "query": query,
        "query_date": query_date,
        "query_subtree": str(args.query_subtree),
        "dictionary": str(args.dictionary),
        "dry_run": args.dry_run,
        "spec_count": len(specs),
        "bindings": bindings,
        "outputs": {
            "flat_csv": str(flat_csv_path),
            "data_bindings": str(output_dir / "data_bindings.json"),
            "materials_index": str(output_dir / "materials_index.json"),
            "node_files": node_files,
        },
    }
    save_json(result, output_dir / "data_bindings.json")
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LogicRAG iFinD data plugin")
    parser.add_argument("--query", required=True, help="User query used to infer the reference date.")
    parser.add_argument("--query-subtree", default=DEFAULT_TEMPLATE, help="query_subtree.json from query_processing.py.")
    parser.add_argument("--dictionary", default=DEFAULT_DICTIONARY, help="domain_dictionary.csv path.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for data bindings.")
    parser.add_argument("--date", default="", help="Override query date as YYYY-MM-DD.")
    parser.add_argument("--asset-name", default="", help="Optional lookup term used only against domain_dictionary.csv.")
    parser.add_argument("--username", default=os.environ.get("IFIND_USERNAME", ""), help="iFinD username.")
    parser.add_argument("--password", default=os.environ.get("IFIND_PASSWORD", ""), help="iFinD password.")
    parser.add_argument("--dry-run", action="store_true", help="Only build query specs; do not call iFinD.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    result = run_data_plugin(args)
    print("LogicRAG iFinD data plugin completed.")
    print(f"- query_date: {result['query_date']}")
    print(f"- spec_count: {result['spec_count']}")
    print(f"- flat_csv: {result['outputs']['flat_csv']}")
    print(f"- data_bindings: {result['outputs']['data_bindings']}")
    if args.dry_run:
        print("- dry_run: iFinD API was not called")


if __name__ == "__main__":
    main()
