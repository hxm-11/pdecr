"""
Convert Excel files to PDF for downstream MinerU processing.

Strategy (ordered by priority):
1. win32com.client  (Windows — requires Microsoft Excel)
2. libreoffice --headless  (cross-platform)
3. Skip with warning  (no usable converter)

All converters return a ``Path`` to the generated PDF, or ``None`` if
that converter is unavailable / fails.
"""

from __future__ import annotations

import logging
import subprocess
import shutil
import os
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Strategy 1: win32com (Excel COM automation) ──

def _excel_to_pdf_win32(file_path: Path, output_dir: Path) -> Path | None:
    """Convert Excel to PDF using Microsoft Excel COM automation.

    Only works on Windows with Excel installed.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        logger.debug("win32com not available — skipping Excel COM path")
        return None

    pdf_path = output_dir / f"{file_path.stem}.pdf"

    pythoncom.CoInitialize()
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        try:
            wb = excel.Workbooks.Open(str(file_path.absolute()))
            # 0 = xlTypePDF
            wb.ExportAsFixedFormat(0, str(pdf_path.absolute()))
            wb.Close(False)
        finally:
            excel.Quit()
    except Exception as exc:
        logger.warning("Excel COM PDF conversion failed: %s", exc)
        return None
    finally:
        pythoncom.CoUninitialize()

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        logger.info("Excel → PDF (win32com): %s", pdf_path.name)
        return pdf_path

    return None


# ── Strategy 2: LibreOffice headless ──

def _excel_to_pdf_libreoffice(file_path: Path, output_dir: Path) -> Path | None:
    """Convert Excel to PDF using LibreOffice in headless mode."""
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if lo_bin is None:
        logger.debug("LibreOffice not found — skipping LO path")
        return None

    pdf_path = output_dir / f"{file_path.stem}.pdf"

    try:
        result = subprocess.run(
            [
                lo_bin,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(output_dir),
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HOME": str(output_dir)},
        )
        logger.debug("LibreOffice stdout: %s", result.stdout)
        if result.returncode != 0:
            logger.warning("LibreOffice stderr: %s", result.stderr)
    except subprocess.TimeoutExpired:
        logger.warning("LibreOffice PDF conversion timed out for %s", file_path.name)
        return None
    except Exception as exc:
        logger.warning("LibreOffice PDF conversion failed: %s", exc)
        return None

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        logger.info("Excel → PDF (libreoffice): %s", pdf_path.name)
        return pdf_path

    return None


# ── Public API ──

def convert_excel_to_pdf(file_path: Path) -> Path | None:
    """Convert an Excel file (.xlsx / .xls) to PDF.

    Returns the path to the generated PDF, or ``None`` if no converter
    is available or all converters fail.  Callers should treat a ``None``
    return as non-fatal — the existing keyword-filtered markdown path
    still provides baseline indexing.
    """
    if not file_path.exists():
        logger.warning("Excel file not found: %s", file_path)
        return None

    suffix = file_path.suffix.lower()
    if suffix not in (".xlsx", ".xlsm", ".xls"):
        logger.warning("Not an Excel file: %s", file_path)
        return None

    output_dir = file_path.parent

    # Strategy 1: win32com
    pdf_path = _excel_to_pdf_win32(file_path, output_dir)
    if pdf_path:
        return pdf_path

    # Strategy 2: LibreOffice
    pdf_path = _excel_to_pdf_libreoffice(file_path, output_dir)
    if pdf_path:
        return pdf_path

    logger.warning(
        "No Excel→PDF converter available for %s. "
        "The file will be indexed via keyword-filtered markdown only. "
        "Install Microsoft Excel or LibreOffice for richer indexing.",
        file_path.name,
    )
    return None
