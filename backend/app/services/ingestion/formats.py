# -*- coding: utf-8 -*-
"""File decoding — turns raw uploaded bytes into a raw DataFrame (CSV/JSON/XML/
Parquet/Excel dispatch) and repairs banner headers.

Public API: _parse_file_bytes, _parse_file_bytes_raw, _fix_banner_header,
_looks_numeric.
Dependencies: ingestion._primitives (_dq), ingestion.columns
(_resolve_columns_verbose). Top of the parsing pipeline. Extracted VERBATIM.
"""
import io  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import re  # noqa: F401
from io import BytesIO, StringIO  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

import eda_metrics  # noqa: F401

from app.core.constants import (  # noqa: F401
    _STANDARD_INTERVALS, _COMMS_STATUS_ALIASES, _COMMS_OK_VALUES,
)

from app.services.ingestion._primitives import _dq  # noqa: F401
from app.services.ingestion.columns import _resolve_columns_verbose  # noqa: F401


def _looks_numeric(v: str) -> bool:
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False

def _fix_banner_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    Real Excel/CSV exports often carry a title banner above the real header
    ("PREDAIOT — Site Export | July 2024" merged across the sheet). pandas
    then reads the banner as the header and every column becomes "Unnamed: N".
    Detect that shape, find the first row that actually looks like a header
    (mostly non-numeric strings across most columns), and re-head the frame.

    Adds a "banner_header_skipped" flag via df.attrs["ingest_flags"] so the
    correction is visible to the operator.
    """
    n_cols = len(df.columns)
    if n_cols == 0 or len(df) == 0:
        return df
    unnamed = sum(1 for c in df.columns
                  if str(c).startswith("Unnamed:") or not str(c).strip())
    if unnamed < max(2, n_cols // 2):
        return df

    for i in range(min(10, len(df))):
        row = df.iloc[i]
        vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if len(vals) < max(2, int(n_cols * 0.6)):
            continue  # banner / blank spacer row
        numericish = sum(1 for v in vals if _looks_numeric(v))
        if numericish > len(vals) * 0.3:
            continue  # data row, not a header
        # Group-band rows ("IDENTIFICATION IDENTIFICATION MARKET MARKET …")
        # repeat a handful of labels; a real header row is nearly all unique.
        if len(set(vals)) < len(vals) * 0.8:
            continue
        new_cols = [str(v).strip() if pd.notna(v) and str(v).strip() else f"col_{j}"
                    for j, v in enumerate(row)]
        out = df.iloc[i + 1:].reset_index(drop=True)
        out.columns = new_cols
        # Restore numeric dtypes the banner header forced to object.
        # Positional access — survives any residual duplicate names.
        for j in range(out.shape[1]):
            num = pd.to_numeric(out.iloc[:, j], errors="coerce")
            if num.notna().mean() >= 0.9:
                out.isetitem(j, num)
        out.attrs["ingest_flags"] = [_dq(
            "info", "banner_header_skipped",
            f"The file starts with {i + 1} title/banner row(s) above the real column "
            "header — skipped automatically.")]
        return out
    return df

def _parse_file_bytes(contents: bytes, filename: str) -> pd.DataFrame:
    """Universal parser + banner-header recovery. See _parse_file_bytes_raw."""
    df = _parse_file_bytes_raw(contents, filename)
    return _fix_banner_header(df)

def _parse_file_bytes_raw(contents: bytes, filename: str) -> pd.DataFrame:
    """
    Universal file parser — handles CSV/TSV/Excel with automatic encoding detection.

    Encoding resolution order:
      1. BOM bytes  →  UTF-16 / UTF-8-BOM
      2. charset_normalizer (pip install charset-normalizer) auto-detect
      3. chardet fallback
      4. Exhaustive encoding list (Western, Arabic, Cyrillic, CJK …)
      5. Force-decode with replacement characters (never raises)
    """
    fname = (filename or "").lower()

    # ── Excel ──────────────────────────────────────────────────────────────────
    if fname.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(BytesIO(contents))

    # ── JSON ───────────────────────────────────────────────────────────────────
    # Accepts:
    #   1) Flat array of records:      [{"time": ..., "price": ...}, ...]
    #   2) Wrapper with a data array:  {"data": [...]}
    #      or {"timeseries": [...]}, {"time_series": [...]}, {"records": [...]},
    #      {"rows": [...]}, {"items": [...]}
    #   3) Column-oriented dict:       {"time": [...], "price": [...]}
    if fname.endswith(".json"):
        try:
            payload = json.loads(contents.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e.msg} at line {e.lineno}") from e
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            for key in ("data", "timeseries", "time_series", "records", "rows", "items", "values"):
                inner = payload.get(key)
                if isinstance(inner, list):
                    return pd.DataFrame(inner)
            # Column-oriented — every value is a list of the same length
            list_cols = {k: v for k, v in payload.items() if isinstance(v, list)}
            if list_cols and len({len(v) for v in list_cols.values()}) == 1:
                return pd.DataFrame(list_cols)
        raise ValueError(
            "JSON must be an array of records, a wrapper like {\"data\": [...]}, "
            "or a column-oriented dict of same-length arrays."
        )

    # ── XML ────────────────────────────────────────────────────────────────────
    # Common in EMS / SCADA historian exports (OSIsoft PI XML, various DCS).
    # pandas.read_xml handles the standard "list of rows" shape without much
    # coaxing. Lazy import so the app boots without lxml installed.
    if fname.endswith(".xml"):
        try:
            # pandas' read_xml uses lxml under the hood; give a clear error if
            # the operator hasn't installed it (this file path is opt-in).
            return pd.read_xml(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "XML upload requires the 'lxml' package. Install with "
                "`pip install lxml` (already declared in requirements.txt)."
            )
        except Exception as e:
            raise ValueError(
                f"Could not parse XML: {e}. Common shape: a root element with "
                "repeated child rows, each row containing scalar fields."
            ) from e

    # ── Parquet ────────────────────────────────────────────────────────────────
    # Data-lake exports. Lazy import — pyarrow is ~50MB, opt-in per deployment.
    if fname.endswith(".parquet"):
        try:
            return pd.read_parquet(BytesIO(contents))
        except ImportError:
            raise ValueError(
                "Parquet upload requires the 'pyarrow' package (~50MB). Install "
                "with `pip install pyarrow` if your deploy environment can afford it."
            )
        except Exception as e:
            raise ValueError(f"Could not parse Parquet: {e}") from e

    # Separator heuristic
    sep = "\t" if fname.endswith(".tsv") else ","

    # ── Encoding resolution, scored by USEFULNESS ──────────────────────────────
    # "Decoded without an exception" is NOT the same as "decoded correctly":
    # cp1256 Arabic bytes decode 'successfully' as Shift-JIS mojibake and the
    # column names become garbage. So every candidate parse is scored by how
    # many internal fields its columns actually resolve to, and the best
    # candidate wins. A score >= 2 (price + an output/consumption column)
    # short-circuits — that parse is definitely the right alphabet.
    def _alias_score(df_cand) -> int:
        try:
            return len(_resolve_columns_verbose([str(c) for c in df_cand.columns])["resolved"])
        except Exception:
            return 0

    ordered = []
    if contents[:2] in (b"\xff\xfe", b"\xfe\xff"):
        ordered.append("utf-16")
    if contents[:3] == b"\xef\xbb\xbf":
        ordered.append("utf-8-sig")
    try:
        from charset_normalizer import from_bytes
        guess = from_bytes(contents[:20000]).best()
        if guess and guess.encoding:
            ordered.append(str(guess.encoding))
    except ImportError:
        pass
    try:
        import chardet
        g = chardet.detect(contents[:20000]).get("encoding")
        if g:
            ordered.append(g)
    except ImportError:
        pass
    ordered += [
        # Unicode
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32",
        # Arabic (كل ملفات Excel المحلية تستخدم هذا) — before Western so Gulf
        # exports don't get eaten by latin-1 (which never raises)
        "cp1256", "iso-8859-6",
        # Western European
        "latin-1", "cp1252", "iso-8859-15",
        # Central / Eastern European
        "cp1250", "iso-8859-2",
        # Cyrillic
        "cp1251", "iso-8859-5", "koi8-r",
        # CJK
        "gbk", "gb2312", "gb18030", "big5", "shift_jis", "euc-jp", "euc-kr",
        # Misc
        "ascii", "cp437",
    ]

    best_df, best_score, tried = None, -1, set()
    for enc in ordered:
        key = enc.lower()
        if key in tried:
            continue
        tried.add(key)
        try:
            df_cand = pd.read_csv(BytesIO(contents), encoding=enc, sep=sep)
        except Exception:
            continue
        if len(df_cand.columns) == 0:
            continue
        score = _alias_score(df_cand)
        if score > best_score:
            best_df, best_score = df_cand, score
        if score >= 2:
            return df_cand
    if best_df is not None:
        return best_df

    # ── Nuclear fallback: force-decode with Unicode replacement chars ───────────
    try:
        text_content = contents.decode("utf-8", errors="replace")
        df = pd.read_csv(StringIO(text_content), sep=sep)
        # Strip replacement chars from column names
        df.columns = [str(c).replace("\ufffd", "").strip() for c in df.columns]
        return df
    except Exception:
        pass

    raise ValueError(
        "Could not parse this file. "
        "Please try: (1) save as CSV UTF-8 in Excel → Save As → CSV UTF-8 (comma delimited), "
        "or (2) export as .xlsx. "
        "Your file's encoding was not recognizable after 20+ attempts."
    )
