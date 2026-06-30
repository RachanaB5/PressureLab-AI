"""
PressureLab AI - Docling Processor
Extracts structured information from match reports, tactical PDFs, and text files.
Uses IBM Docling when available, falls back to robust text extraction.
"""

import logging
import re
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to bundled match report
REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
DEFAULT_REPORT = REPORT_DIR / "france_croatia_2018_report.txt"


class DoclingProcessor:
    """
    Processes documents using IBM Docling when available.
    Falls back to robust text extraction for .txt and .pdf files.
    Provides chunking for RAG pipelines.
    """

    def __init__(self):
        self._converter = None
        self._docling_available = False
        self._knowledge_base_cache: Optional[dict] = None
        self._try_import_docling()

    def _try_import_docling(self):
        """Check if docling is importable."""
        try:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
            self._docling_available = True
            logger.info("Docling converter initialized successfully")
        except ImportError:
            logger.info("Docling not installed — using built-in text extraction fallback")
        except Exception as e:
            logger.warning(f"Docling initialization failed: {e} — using fallback")

    # ────────────────────────────────────────────────────────────────────────
    # Core document processing
    # ────────────────────────────────────────────────────────────────────────

    def process_document(self, file_path: str) -> dict:
        """
        Process a document and extract structured content.
        Uses Docling for PDFs when available, fallback for text files.

        Returns:
            dict with 'text', 'tables', 'sections', 'source'
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return {
                'text': '',
                'tables': [],
                'sections': [],
                'source': file_path,
                'error': 'File not found',
            }

        # Try Docling for PDF files
        if self._docling_available and path.suffix.lower() == '.pdf':
            return self._process_with_docling(file_path)

        # Fallback text extraction
        return self._process_text_file(file_path)

    def process_match_report(self, file_path: str) -> dict:
        """
        Process a match report and extract structured sections, tables, and text.

        Returns:
            dict with raw_text, statistics_tables, sections, source, type
        """
        content = self.process_document(file_path)

        return {
            'raw_text': content.get('text', ''),
            'statistics_tables': content.get('tables', []),
            'sections': content.get('sections', []),
            'chunks': self.chunk_document(content.get('text', ''), chunk_size=500),
            'source': file_path,
            'type': 'match_report',
        }

    def chunk_document(self, text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
        """
        Create overlapping text chunks suitable for RAG retrieval.

        Args:
            text: The full document text
            chunk_size: Target number of characters per chunk
            overlap: Number of overlapping characters between chunks

        Returns:
            list of dicts with 'chunk_id', 'text', 'start_char', 'end_char'
        """
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at a sentence or paragraph boundary
            if end < len(text):
                # Look for the last period/newline within the chunk
                last_break = text.rfind('\n\n', start, end)
                if last_break == -1 or last_break <= start:
                    last_break = text.rfind('. ', start, end)
                if last_break == -1 or last_break <= start:
                    last_break = text.rfind('\n', start, end)
                if last_break > start:
                    end = last_break + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    'chunk_id': chunk_id,
                    'text': chunk_text,
                    'start_char': start,
                    'end_char': end,
                })
                chunk_id += 1

            # Move forward by chunk_size minus overlap
            start = max(start + 1, end - overlap)
            if start >= len(text):
                break

        logger.info(f"Chunked document into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
        return chunks

    def get_match_knowledge_base(self) -> dict:
        """
        Return pre-processed tactical knowledge about the 2018 World Cup Final
        from the bundled report file.

        Returns:
            dict with 'raw_text', 'sections', 'chunks', 'tables', 'source'
        """
        if self._knowledge_base_cache is not None:
            return self._knowledge_base_cache

        if DEFAULT_REPORT.exists():
            logger.info(f"Loading knowledge base from {DEFAULT_REPORT}")
            result = self.process_match_report(str(DEFAULT_REPORT))
            self._knowledge_base_cache = result
            return result

        logger.warning(f"Knowledge base file not found at {DEFAULT_REPORT}")
        return {
            'raw_text': '',
            'sections': [],
            'chunks': [],
            'tables': [],
            'source': str(DEFAULT_REPORT),
            'type': 'match_report',
            'error': 'Report file not found',
        }

    # ────────────────────────────────────────────────────────────────────────
    # Docling processing
    # ────────────────────────────────────────────────────────────────────────

    def _process_with_docling(self, file_path: str) -> dict:
        """Process using IBM Docling."""
        try:
            result = self._converter.convert(file_path)

            markdown_text = result.document.export_to_markdown()

            tables = []
            for table in result.document.tables:
                try:
                    df = table.export_to_dataframe()
                    tables.append({
                        'headers': list(df.columns),
                        'rows': df.values.tolist(),
                    })
                except Exception:
                    pass

            sections = []
            for item, level in result.document.iterate_items():
                item_type = type(item).__name__
                if item_type in ['TextItem', 'SectionHeaderItem']:
                    sections.append({
                        'type': item_type,
                        'level': level,
                        'text': str(item),
                    })

            return {
                'text': markdown_text,
                'tables': tables,
                'sections': sections,
                'source': file_path,
                'processor': 'docling',
            }

        except Exception as e:
            logger.error(f"Docling processing error: {e}")
            return self._process_text_file(file_path)

    # ────────────────────────────────────────────────────────────────────────
    # Robust fallback text extraction
    # ────────────────────────────────────────────────────────────────────────

    def _process_text_file(self, file_path: str) -> dict:
        """
        Robust fallback processor for text (and simple PDF) files.
        Extracts sections, tables, and text structure from plain text files.
        For PDFs without Docling, attempts basic text extraction.
        """
        path = Path(file_path)

        text = ""
        if path.suffix.lower() == '.pdf':
            text = self._extract_pdf_text_fallback(file_path)
        else:
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                text = path.read_text(encoding='latin-1')
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return {
                    'text': '',
                    'tables': [],
                    'sections': [],
                    'source': file_path,
                    'error': str(e),
                }

        # Extract sections by detecting headers (lines of ═══ or ALL CAPS lines)
        sections = self._extract_sections(text)

        # Extract any tables (simple ASCII tables)
        tables = self._extract_simple_tables(text)

        return {
            'text': text,
            'tables': tables,
            'sections': sections,
            'source': file_path,
            'processor': 'fallback',
        }

    def _extract_pdf_text_fallback(self, file_path: str) -> str:
        """Try to extract text from PDF without Docling."""
        # Try PyPDF2 / pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages = [page.extract_text() or '' for page in reader.pages]
            text = '\n\n'.join(pages)
            if text.strip():
                logger.info(f"Extracted text from PDF using pypdf: {len(text)} chars")
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pypdf extraction failed: {e}")

        # Try pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages = [page.extract_text() or '' for page in pdf.pages]
            text = '\n\n'.join(pages)
            if text.strip():
                logger.info(f"Extracted text from PDF using pdfplumber: {len(text)} chars")
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

        logger.warning(f"No PDF text extractor available for {file_path}")
        return f"[PDF content from {file_path} — install docling or pypdf for extraction]"

    def _extract_sections(self, text: str) -> list[dict]:
        """Extract section structure from plain text."""
        sections = []
        lines = text.split('\n')
        current_section = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect section dividers (═══ or ─── patterns)
            if re.match(r'^[═─]{5,}$', stripped):
                continue

            # Detect section headers: SECTION N: TITLE or ALL CAPS with colon
            section_match = re.match(r'^SECTION\s+\d+:\s*(.+)$', stripped)
            if section_match:
                current_section = section_match.group(1).strip()
                sections.append({
                    'type': 'SectionHeader',
                    'level': 1,
                    'text': current_section,
                    'line': i + 1,
                })
                continue

            # Detect sub-headers: MINUTE XX — or all-caps lines > 10 chars
            minute_match = re.match(r'^MINUTE\s+\d+.*$', stripped)
            if minute_match:
                sections.append({
                    'type': 'SubHeader',
                    'level': 2,
                    'text': stripped,
                    'line': i + 1,
                })
                continue

            # Player name headers (ALL CAPS name followed by —)
            player_match = re.match(r'^([A-Z][A-Za-zÀ-ÿ\s\']+)\s*—\s*(.+)$', stripped)
            if player_match and len(stripped) > 15:
                sections.append({
                    'type': 'PlayerNote',
                    'level': 3,
                    'text': stripped,
                    'line': i + 1,
                })

        return sections

    def _extract_simple_tables(self, text: str) -> list[dict]:
        """Extract simple statistics tables from text."""
        tables = []

        # Find lines that look like "- Stat: Team1 X - Team2 Y" patterns
        stat_lines = re.findall(
            r'-\s*(\w[\w\s]+?):\s*(\w[\w\s]+?)\s+(\d+%?)\s*-\s*(\w[\w\s]+?)\s+(\d+%?)',
            text
        )

        if stat_lines:
            headers = ['Statistic', 'Team 1', 'Value 1', 'Team 2', 'Value 2']
            rows = [[s[0].strip(), s[1].strip(), s[2], s[3].strip(), s[4]] for s in stat_lines]
            tables.append({
                'headers': headers,
                'rows': rows,
            })

        return tables
