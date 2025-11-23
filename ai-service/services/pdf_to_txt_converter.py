"""
PDF to Text Converter Service

Converts CV PDF files to plain text format with optional formatting preservation.
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import hashlib

# PDF processing
import PyPDF2
import pdfplumber

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFToTextConverter:
    """
    Service to convert PDF files to plain text format.
    Supports multiple extraction methods with fallback.
    """
    
    def __init__(self, output_dir: str = "converted_cvs"):
        """
        Initialize the PDF to text converter.
        
        Args:
            output_dir: Directory to save converted text files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"PDF to Text Converter initialized. Output directory: {output_dir}")
    
    def convert_pdf_to_text(
        self, 
        pdf_path: str, 
        output_filename: Optional[str] = None,
        preserve_formatting: bool = True,
        method: str = "auto"
    ) -> Dict[str, Any]:
        """
        Convert a PDF file to plain text.
        
        Args:
            pdf_path: Path to the PDF file
            output_filename: Optional custom output filename (without extension)
            preserve_formatting: Whether to preserve formatting and layout
            method: Extraction method - 'auto', 'pdfplumber', 'pypdf2'
            
        Returns:
            Dictionary with conversion results:
            {
                "success": bool,
                "text_file_path": str,
                "original_file": str,
                "text_length": int,
                "method_used": str,
                "converted_at": str
            }
        """
        start_time = datetime.utcnow()
        
        # Validate input file
        if not os.path.exists(pdf_path):
            return {
                "success": False,
                "error": f"PDF file not found: {pdf_path}"
            }
        
        if not pdf_path.lower().endswith('.pdf'):
            return {
                "success": False,
                "error": f"File is not a PDF: {pdf_path}"
            }
        
        try:
            # Extract text based on method
            if method == "auto":
                text, method_used = self._extract_text_auto(pdf_path, preserve_formatting)
            elif method == "pdfplumber":
                text = self._extract_with_pdfplumber(pdf_path, preserve_formatting)
                method_used = "pdfplumber"
            elif method == "pypdf2":
                text = self._extract_with_pypdf2(pdf_path)
                method_used = "pypdf2"
            else:
                return {
                    "success": False,
                    "error": f"Unknown extraction method: {method}"
                }
            
            # Generate output filename
            if output_filename:
                txt_filename = f"{output_filename}.txt"
            else:
                original_name = Path(pdf_path).stem
                txt_filename = f"{original_name}.txt"
            
            txt_path = os.path.join(self.output_dir, txt_filename)
            
            # Save to text file
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"Converted {pdf_path} to {txt_path} in {duration:.2f}s using {method_used}")
            
            return {
                "success": True,
                "text_file_path": txt_path,
                "original_file": pdf_path,
                "text_length": len(text),
                "method_used": method_used,
                "converted_at": start_time.isoformat(),
                "duration_seconds": round(duration, 2)
            }
            
        except Exception as e:
            logger.error(f"Error converting PDF to text: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_file": pdf_path
            }
    
    def convert_pdf_bytes_to_text(
        self,
        pdf_content: bytes,
        filename: str,
        preserve_formatting: bool = True
    ) -> Dict[str, Any]:
        """
        Convert PDF from bytes to text file.
        
        Args:
            pdf_content: PDF file content as bytes
            filename: Original filename (for naming the output)
            preserve_formatting: Whether to preserve formatting
            
        Returns:
            Dictionary with conversion results
        """
        # Save bytes to temporary file
        temp_pdf_path = os.path.join(self.output_dir, f"temp_{filename}")
        
        try:
            with open(temp_pdf_path, 'wb') as f:
                f.write(pdf_content)
            
            # Convert using the file-based method
            result = self.convert_pdf_to_text(
                temp_pdf_path,
                output_filename=Path(filename).stem,
                preserve_formatting=preserve_formatting
            )
            
            # Clean up temp file
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            
            return result
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            
            return {
                "success": False,
                "error": str(e),
                "original_file": filename
            }
    
    def batch_convert(
        self,
        pdf_directory: str,
        file_pattern: str = "*.pdf",
        preserve_formatting: bool = True
    ) -> Dict[str, Any]:
        """
        Convert multiple PDF files in a directory to text.
        
        Args:
            pdf_directory: Directory containing PDF files
            file_pattern: Glob pattern to match PDF files
            preserve_formatting: Whether to preserve formatting
            
        Returns:
            Dictionary with batch conversion results
        """
        if not os.path.exists(pdf_directory):
            return {
                "success": False,
                "error": f"Directory not found: {pdf_directory}"
            }
        
        pdf_files = list(Path(pdf_directory).glob(file_pattern))
        
        if not pdf_files:
            return {
                "success": False,
                "error": f"No PDF files found in {pdf_directory} matching {file_pattern}"
            }
        
        results = {
            "total_files": len(pdf_files),
            "successful": 0,
            "failed": 0,
            "conversions": []
        }
        
        for pdf_file in pdf_files:
            result = self.convert_pdf_to_text(
                str(pdf_file),
                preserve_formatting=preserve_formatting
            )
            
            if result["success"]:
                results["successful"] += 1
            else:
                results["failed"] += 1
            
            results["conversions"].append(result)
        
        logger.info(f"Batch conversion completed: {results['successful']}/{results['total_files']} successful")
        
        return results
    
    def _extract_text_auto(self, pdf_path: str, preserve_formatting: bool) -> tuple:
        """
        Automatically choose the best extraction method.
        Tries pdfplumber first, falls back to PyPDF2.
        
        Returns:
            Tuple of (text, method_used)
        """
        try:
            text = self._extract_with_pdfplumber(pdf_path, preserve_formatting)
            return text, "pdfplumber"
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}. Trying PyPDF2...")
            try:
                text = self._extract_with_pypdf2(pdf_path)
                return text, "pypdf2"
            except Exception as e2:
                logger.error(f"Both extraction methods failed: {e2}")
                raise
    
    def _extract_with_pdfplumber(self, pdf_path: str, preserve_formatting: bool) -> str:
        """Extract text using pdfplumber (better formatting preservation)"""
        text_parts = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                
                if page_text:
                    if preserve_formatting:
                        # Add page separator
                        text_parts.append(f"\n{'='*60}\n")
                        text_parts.append(f"Page {page_num}\n")
                        text_parts.append(f"{'='*60}\n\n")
                    
                    text_parts.append(page_text)
                    text_parts.append("\n\n")
        
        return "".join(text_parts).strip()
    
    def _extract_with_pypdf2(self, pdf_path: str) -> str:
        """Extract text using PyPDF2 (fallback method)"""
        text_parts = []
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                
                if page_text:
                    text_parts.append(f"\n--- Page {page_num} ---\n")
                    text_parts.append(page_text)
                    text_parts.append("\n\n")
        
        return "".join(text_parts).strip()
    
    def get_text_preview(self, pdf_path: str, max_chars: int = 500) -> str:
        """
        Get a preview of the PDF text content.
        
        Args:
            pdf_path: Path to PDF file
            max_chars: Maximum characters to return
            
        Returns:
            Text preview
        """
        try:
            text, _ = self._extract_text_auto(pdf_path, preserve_formatting=False)
            preview = text[:max_chars]
            
            if len(text) > max_chars:
                preview += "..."
            
            return preview
        except Exception as e:
            return f"Error generating preview: {e}"
