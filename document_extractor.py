import os
import io
import re
import shutil
import logging
import unicodedata
from typing import Dict, Any, Tuple

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("document_extractor")

# PyMuPDF import using supported non-deprecated namespace
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import docx
except ImportError:
    docx = None


# ---------------------------------------------------------------------------
# Robust Tesseract Executable Detection (Local Windows + Linux / Render PATH)
# ---------------------------------------------------------------------------

def get_tesseract_status() -> Tuple[bool, str]:
    """
    Detect whether pytesseract library is installed AND the system Tesseract
    binary executable is available. Supports TESSERACT_CMD env variable,
    system PATH (via shutil.which), and common Windows installation paths.
    Returns (available: bool, executable_path: str|None).
    """
    if pytesseract is None:
        return False, None

    # 1. Environment variable override
    tess_cmd = os.getenv("TESSERACT_CMD")
    if tess_cmd and os.path.exists(tess_cmd):
        pytesseract.pytesseract.tesseract_cmd = tess_cmd
        return True, tess_cmd

    # 2. System PATH lookup (Works on Linux, Render, Docker, and Windows PATH)
    which_path = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = which_path
        return True, which_path

    # 3. Standard Windows installation paths
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True, path

    return False, None


# ---------------------------------------------------------------------------
# Text Quality & Cleaning Helper Functions
# ---------------------------------------------------------------------------

def clean_extracted_text(text: str) -> str:
    """
    Clean and normalize extracted resume text while preserving structure,
    bullet points, emails, phone numbers, tech symbols, and line breaks.
    """
    if not text:
        return ""

    # Replace null bytes
    text = text.replace('\x00', ' ')

    # Normalize unicode to NFC
    text = unicodedata.normalize('NFC', text)

    # Normalize line endings to \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Replace non-breaking spaces and unusual whitespace
    text = re.sub(r'[\xa0\u2000-\u200b\u202f\u205f\u3000]', ' ', text)

    # Clean horizontal white space on each line (preserve indentation/bullet alignment)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
        cleaned_lines.append(cleaned_line)

    text = '\n'.join(cleaned_lines)

    # Remove excessive blank lines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def is_good_text(text: str, is_page: bool = False) -> bool:
    """
    Evaluate if extracted text is readable resume text or garbage/empty.
    Preserves legitimate resumes containing tech terms (C++, .NET, SQL, Python),
    bullet points, emails, numbers, URLs, and phone numbers.
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()
    min_len = 25 if is_page else 45
    if len(cleaned) < min_len:
        return False

    total_chars = len(cleaned)

    # Count alphabetic characters
    alpha_chars = len(re.findall(r'[a-zA-Z]', cleaned))
    alpha_ratio = alpha_chars / total_chars

    # Minimum alphabetic character requirement
    min_alpha = 10 if is_page else 20
    if alpha_chars < min_alpha or alpha_ratio < 0.20:
        return False

    # Count printable characters
    printable_chars = sum(1 for c in cleaned if c.isprintable() or c in '\n\t')
    printable_ratio = printable_chars / total_chars
    if printable_ratio < 0.70:
        return False

    # Check for suspicious replacement/garbage unicode characters (e.g. Ã©, Â, ÿ, þ, )
    garbage_chars = len(re.findall(r'[\ufffd\x00-\x08\x0b\x0c\x0e-\x1fÃÂÿþ]', cleaned))
    if garbage_chars / total_chars > 0.08:
        return False

    # Check for repeated garbage symbol clusters (e.g. "%%%%%%%", "!!!!!!!")
    if re.search(r'([^\w\s])\1{7,}', cleaned):
        return False

    # Count meaningful words (words with at least 2 alphabetic letters)
    words = re.findall(r'\b[a-zA-Z]{2,}\b', cleaned)
    min_words = 4 if is_page else 8
    if len(words) < min_words:
        return False

    return True


# ---------------------------------------------------------------------------
# PDF Layout-Aware Extraction (Two-Column & Multi-Column Sorting)
# ---------------------------------------------------------------------------

def _extract_page_blocks_sorted(page) -> str:
    """
    Extract text blocks from a PyMuPDF page and sort them logically
    to handle multi-column layouts correctly.
    """
    if not hasattr(page, "get_text"):
        return ""

    blocks = page.get_text("blocks")
    if not blocks:
        return ""

    text_blocks = [b for b in blocks if len(b) >= 7 and b[6] == 0 and b[4].strip()]
    if not text_blocks:
        return ""

    page_rect = page.rect
    page_width = page_rect.width if page_rect else 600
    page_height = page_rect.height if page_rect else 800

    mid_x = page_width / 2.0
    left_blocks = []
    right_blocks = []
    header_blocks = []
    footer_blocks = []

    for b in text_blocks:
        x0, y0, x1, y1, b_text = b[0], b[1], b[2], b[3], b[4]
        b_width = x1 - x0

        # Header: spans > 55% of page width or top 12% of page height
        if b_width > 0.55 * page_width or y0 < 0.12 * page_height:
            header_blocks.append(b)
        # Footer: bottom 8% of page
        elif y1 > 0.92 * page_height:
            footer_blocks.append(b)
        # Left column
        elif (x0 + x1) / 2.0 < mid_x:
            left_blocks.append(b)
        # Right column
        else:
            right_blocks.append(b)

    # Sort each section vertically by y0, then x0
    header_blocks.sort(key=lambda b: (b[1], b[0]))
    left_blocks.sort(key=lambda b: (b[1], b[0]))
    right_blocks.sort(key=lambda b: (b[1], b[0]))
    footer_blocks.sort(key=lambda b: (b[1], b[0]))

    ordered_blocks = header_blocks + left_blocks + right_blocks + footer_blocks
    text_parts = [b[4].strip() for b in ordered_blocks]

    return "\n\n".join(text_parts)


# ---------------------------------------------------------------------------
# OCR Fallback Implementation
# ---------------------------------------------------------------------------

def _ocr_page(page) -> str:
    """
    Perform Tesseract OCR on a single PyMuPDF PDF page when text is unreadable or scanned.
    Renders page at 250 DPI for optimal accuracy without excessive RAM overhead.
    """
    tess_available, tess_exec = get_tesseract_status()
    if not tess_available or Image is None:
        logger.warning("Tesseract OCR executable is not available on this system. Skipping page OCR.")
        return ""

    try:
        # Render page at 250 DPI
        pix = page.get_pixmap(dpi=250)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Try PSM 6 (Assume a single uniform block of text)
        ocr_text = pytesseract.image_to_string(img, config='--psm 6')

        if not is_good_text(ocr_text, is_page=True):
            # Fallback to default PSM mode if PSM 6 yielded poor results
            ocr_text = pytesseract.image_to_string(img)

        return ocr_text.strip()
    except Exception as e:
        logger.warning(f"OCR execution failed on page: {e}")
        return ""


# ---------------------------------------------------------------------------
# Main Extraction Logic: PDF and DOCX
# ---------------------------------------------------------------------------

def extract_pdf_text(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """
    Perform layered page-by-page text extraction for PDFs.
    Flow per page: PyMuPDF layout blocks -> PyPDF fallback -> OCR fallback per page.
    """
    page_texts = []
    page_methods = []
    errors = []

    tess_avail, tess_path = get_tesseract_status()

    doc = None
    if fitz:
        try:
            doc = fitz.open(filepath)
        except Exception as e:
            errors.append(f"PyMuPDF failed to open PDF: {e}")
            doc = None

    if doc is not None:
        try:
            if getattr(doc, "is_encrypted", False):
                errors.append("PDF is encrypted or password protected")
            else:
                num_pages = len(doc)
                for page_idx in range(num_pages):
                    page = doc[page_idx]
                    page_text = ""
                    method = "none"

                    # 1. Try PyMuPDF multi-column block extraction
                    try:
                        page_text = _extract_page_blocks_sorted(page)
                        if is_good_text(page_text, is_page=True):
                            method = "pymupdf_blocks"
                    except Exception as e:
                        logger.debug(f"PyMuPDF block extraction failed on page {page_idx + 1}: {e}")

                    # 2. Try standard PyMuPDF page text
                    if not is_good_text(page_text, is_page=True):
                        try:
                            std_text = page.get_text() or ""
                            if is_good_text(std_text, is_page=True):
                                page_text = std_text
                                method = "pymupdf_standard"
                        except Exception as e:
                            logger.debug(f"PyMuPDF standard extraction failed on page {page_idx + 1}: {e}")

                    # 3. Try pypdf / PyPDF2 fallback for this page
                    if not is_good_text(page_text, is_page=True):
                        pypdf_text = _extract_pdf_page_with_pypdf(filepath, page_idx)
                        if is_good_text(pypdf_text, is_page=True):
                            page_text = pypdf_text
                            method = "pypdf"

                    # 4. OCR fallback for this specific page if text is still bad/scanned
                    if not is_good_text(page_text, is_page=True):
                        ocr_text = _ocr_page(page)
                        if is_good_text(ocr_text, is_page=True):
                            page_text = ocr_text
                            method = "ocr"
                        elif ocr_text and len(ocr_text) > len(page_text):
                            page_text = ocr_text
                            method = "ocr_partial"

                    page_texts.append(page_text)
                    page_methods.append(method)

        except Exception as e:
            errors.append(f"Error reading PDF page: {e}")
        finally:
            try:
                doc.close()
            except Exception:
                pass

    # If PyMuPDF couldn't open the PDF, try full pypdf extraction
    if not page_texts:
        full_pypdf = _extract_full_pdf_with_pypdf(filepath)
        if full_pypdf:
            page_texts.append(full_pypdf)
            page_methods.append("pypdf_full")

    combined_text = "\n\n".join(t for t in page_texts if t.strip())
    cleaned_text = clean_extracted_text(combined_text)

    is_valid = is_good_text(cleaned_text, is_page=False)

    metadata = {
        "success": is_valid,
        "page_methods": page_methods,
        "extracted_length": len(cleaned_text),
        "tesseract_available": tess_avail,
        "tesseract_executable": tess_path,
        "errors": errors
    }

    logger.info(f"PDF Extraction completed for '{os.path.basename(filepath)}': length={len(cleaned_text)}, page_methods={page_methods}, tesseract_avail={tess_avail}")

    return cleaned_text, metadata


def _extract_pdf_page_with_pypdf(filepath: str, page_idx: int) -> str:
    """Extract a single page's text using pypdf or PyPDF2."""
    if pypdf:
        try:
            reader = pypdf.PdfReader(filepath)
            if page_idx < len(reader.pages):
                return reader.pages[page_idx].extract_text() or ""
        except Exception:
            pass

    if PyPDF2:
        try:
            reader = PyPDF2.PdfReader(filepath)
            if page_idx < len(reader.pages):
                return reader.pages[page_idx].extract_text() or ""
        except Exception:
            pass

    return ""


def _extract_full_pdf_with_pypdf(filepath: str) -> str:
    """Extract all text using pypdf / PyPDF2."""
    text_parts = []
    if pypdf:
        try:
            reader = pypdf.PdfReader(filepath)
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    text_parts.append(t)
            return "\n\n".join(text_parts)
        except Exception:
            pass

    if PyPDF2:
        try:
            reader = PyPDF2.PdfReader(filepath)
            for p in reader.pages:
                t = p.extract_text()
                if t:
                    text_parts.append(t)
            return "\n\n".join(text_parts)
        except Exception:
            pass

    return ""


def extract_docx_text(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract structured text from DOCX files, including paragraphs,
    headings, tables, and headers/footers.
    """
    if docx is None:
        return "", {"success": False, "error": "python-docx package is not installed"}

    text_parts = []
    try:
        doc = docx.Document(filepath)

        # Extract headers
        for section in doc.sections:
            if section.header:
                for hp in section.header.paragraphs:
                    if hp.text.strip():
                        text_parts.append(hp.text.strip())

        # Extract body paragraphs and tables in sequence
        for elem in doc.element.body:
            if elem.tag.endswith('p'):
                p = docx.text.paragraph.Paragraph(elem, doc)
                if p.text.strip():
                    text_parts.append(p.text.strip())
            elif elem.tag.endswith('tbl'):
                tbl = docx.table.Table(elem, doc)
                for row in tbl.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        text_parts.append(" | ".join(row_cells))

        combined_text = "\n".join(text_parts)
        cleaned_text = clean_extracted_text(combined_text)
        is_valid = is_good_text(cleaned_text, is_page=False)

        return cleaned_text, {
            "success": is_valid,
            "extracted_length": len(cleaned_text),
            "method": "docx"
        }
    except Exception as e:
        logger.error(f"Error reading DOCX file {filepath}: {e}")
        return "", {"success": False, "error": str(e), "method": "docx"}


def extract_document_text(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """
    Main unified extraction entry point.
    Handles case-insensitive extension checking (.pdf, .PDF, .docx, .DOCX).
    Returns (cleaned_text, metadata_dict).
    """
    if not filepath or not os.path.exists(filepath):
        return "", {"success": False, "error": "File does not exist"}

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return extract_pdf_text(filepath)
    elif ext in [".docx", ".doc"]:
        return extract_docx_text(filepath)
    else:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            cleaned = clean_extracted_text(content)
            return cleaned, {"success": is_good_text(cleaned), "method": "plain_text"}
        except Exception as e:
            return "", {"success": False, "error": f"Unsupported format {ext}: {e}"}
