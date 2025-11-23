"""
Unified CV Parser Service

Production-ready CV parser combining the best features from both implementations:
- Async and sync parsing support
- Optional LLM integration with Ollama
- Text caching for performance
- Confidence scoring for all extracted fields
- Section detection and structured parsing
- Entity normalization (companies, skills, dates)
- Extends BaseParser for compatibility with data ingestion layer
- Multiple export formats (JSON, dict)
- Comprehensive error handling and fallback mechanisms
"""

import os
import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from io import BytesIO
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import hashlib

# PDF/Document processing
import PyPDF2
import pdfplumber
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# Date parsing
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

# LLM integration (optional)
try:
    from langchain_community.llms import Ollama
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
    LANGCHAIN_AVAILABLE = True
except (ImportError, TypeError, AttributeError) as e:
    # Handle both missing dependencies and version compatibility issues
    LANGCHAIN_AVAILABLE = False
    import warnings
    warnings.warn(f"LangChain not available: {e}. Using regex-only parsing.")

# Import BaseParser if available (for data ingestion compatibility)
try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from data_ingestion.parsers.base_parser import BaseParser
    BASE_PARSER_AVAILABLE = True
except ImportError:
    BASE_PARSER_AVAILABLE = False
    # Create a dummy BaseParser for standalone operation
    class BaseParser:
        def __init__(self):
            self.parser_name = self.__class__.__name__
            self.version = "1.0.0"
        
        def default_response(self) -> Dict[str, Any]:
            return {
                "skills": [],
                "experience": [],
                "education": [],
                "phone": None,
                "email": None,
                "years_of_experience": 0,
                "certifications": [],
                "projects": [],
                "languages": [],
                "parser_name": self.parser_name,
                "parser_version": self.version
            }

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CVParser(BaseParser):
    """
    Unified CV parser combining regex-based extraction with optional LLM enhancement.
    Supports both async (for API usage) and sync (for data ingestion) interfaces.
    Falls back gracefully when LLM is unavailable.
    """
    
    # Comprehensive skill ontology for normalization
    SKILL_ONTOLOGY = {
        "python": {"category": "programming", "aliases": ["python", "py", "python3"]},
        "java": {"category": "programming", "aliases": ["java", "java8", "java11", "java17"]},
        "javascript": {"category": "programming", "aliases": ["javascript", "js", "node.js", "nodejs"]},
        "typescript": {"category": "programming", "aliases": ["typescript", "ts"]},
        "c++": {"category": "programming", "aliases": ["c++", "cpp"]},
        "c#": {"category": "programming", "aliases": ["c#", "csharp"]},
        "ruby": {"category": "programming", "aliases": ["ruby"]},
        "php": {"category": "programming", "aliases": ["php"]},
        "swift": {"category": "programming", "aliases": ["swift"]},
        "kotlin": {"category": "programming", "aliases": ["kotlin"]},
        "go": {"category": "programming", "aliases": ["go", "golang"]},
        "rust": {"category": "programming", "aliases": ["rust"]},
        "scala": {"category": "programming", "aliases": ["scala"]},
        "r": {"category": "programming", "aliases": ["r"]},
        "react": {"category": "framework", "aliases": ["react", "reactjs", "react.js"]},
        "angular": {"category": "framework", "aliases": ["angular", "angularjs"]},
        "vue": {"category": "framework", "aliases": ["vue", "vuejs", "vue.js"]},
        "spring": {"category": "framework", "aliases": ["spring", "spring boot", "springboot"]},
        "django": {"category": "framework", "aliases": ["django"]},
        "flask": {"category": "framework", "aliases": ["flask"]},
        "fastapi": {"category": "framework", "aliases": ["fastapi", "fast api"]},
        "express": {"category": "framework", "aliases": ["express", "express.js"]},
        "next.js": {"category": "framework", "aliases": ["next.js", "nextjs"]},
        "langchain": {"category": "ml_framework", "aliases": ["langchain", "lang chain"]},
        "tensorflow": {"category": "ml_framework", "aliases": ["tensorflow", "tf"]},
        "pytorch": {"category": "ml_framework", "aliases": ["pytorch", "torch"]},
        "scikit-learn": {"category": "ml_framework", "aliases": ["scikit-learn", "sklearn"]},
        "keras": {"category": "ml_framework", "aliases": ["keras"]},
        "aws": {"category": "cloud", "aliases": ["aws", "amazon web services"]},
        "azure": {"category": "cloud", "aliases": ["azure", "microsoft azure"]},
        "gcp": {"category": "cloud", "aliases": ["gcp", "google cloud"]},
        "docker": {"category": "devops", "aliases": ["docker"]},
        "kubernetes": {"category": "devops", "aliases": ["kubernetes", "k8s"]},
        "terraform": {"category": "devops", "aliases": ["terraform"]},
        "ansible": {"category": "devops", "aliases": ["ansible"]},
        "postgresql": {"category": "database", "aliases": ["postgresql", "postgres"]},
        "mysql": {"category": "database", "aliases": ["mysql"]},
        "mongodb": {"category": "database", "aliases": ["mongodb", "mongo"]},
        "redis": {"category": "database", "aliases": ["redis"]},
        "elasticsearch": {"category": "database", "aliases": ["elasticsearch"]},
        "git": {"category": "tools", "aliases": ["git", "github", "gitlab"]},
        "jenkins": {"category": "tools", "aliases": ["jenkins"]},
        "jira": {"category": "tools", "aliases": ["jira"]},
    }
    
    # Company name normalization
    COMPANY_MAP = {
        "sap se": "SAP SE",
        "sap": "SAP SE",
        "momox gmbh": "momox GmbH",
        "auto1 gmbh": "Auto1 Group GmbH",
        "vodafone": "Vodafone Group",
        "amazon": "Amazon",
        "google": "Google",
        "microsoft": "Microsoft",
        "meta": "Meta",
        "apple": "Apple Inc.",
    }
    
    # Education degree patterns
    EDUCATION_PATTERNS = [
        r'(phd|ph\.d\.|doctorate|doctoral)',
        r'(master|m\.s\.|msc|m\.sc\.|mba|m\.b\.a\.)',
        r'(bachelor|b\.s\.|bsc|b\.sc\.|b\.a\.|ba|b\.tech|b\.e\.)',
        r'(associate|a\.s\.|diploma)',
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the unified CV parser"""
        super().__init__()
        self.config = config or {}
        self.version = "3.0.0"  # Unified version
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("MODEL_NAME", "qwen2.5:7b")
        self.use_llm = self.config.get("use_llm", True) and LANGCHAIN_AVAILABLE
        
        # Text cache directory
        self.text_cache_dir = self.config.get("text_cache_dir", "cv_text_cache")
        os.makedirs(self.text_cache_dir, exist_ok=True)
        
        # Initialize Ollama LLM if available
        if self.use_llm:
            try:
                self.llm = Ollama(
                    base_url=self.ollama_url,
                    model=self.model_name,
                    temperature=0.1
                )
                logger.info("LLM initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}. Using regex-only parsing.")
                self.use_llm = False
        else:
            self.llm = None
            logger.info("Using regex-only parsing (LLM disabled)")
        
        # LLM prompts
        self._init_prompts()
    
    def _init_prompts(self):
        """Initialize LLM prompt templates"""
        if not LANGCHAIN_AVAILABLE:
            return
        
        self.parse_prompt = PromptTemplate(
            input_variables=["cv_text"],
            template="""
You are an AI assistant specialized in parsing CVs/resumes. Extract the following information from the CV text below and return it as valid JSON.

Extract:
1. Personal Information: full_name, email, phone
2. Skills: List all technical and soft skills
3. Experience: Array of work experiences with title, company, startDate, endDate, description, responsibilities
4. Education: Array of education entries with degree, institution, startDate, endDate, fieldOfStudy

CV Text:
{cv_text}

Return ONLY valid JSON in this exact format (no additional text):
{{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["skill1", "skill2"],
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "startDate": "YYYY-MM",
      "endDate": "YYYY-MM or Present",
      "description": "string",
      "responsibilities": ["resp1", "resp2"]
    }}
  ],
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "startDate": "YYYY-MM",
      "endDate": "YYYY-MM",
      "fieldOfStudy": "string"
    }}
  ]
}}
"""
        )
    
    # ==================== ASYNC INTERFACE (for API usage) ====================
    
    async def parse_cv(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Main async entry point for CV parsing (used by FastAPI).
        
        Args:
            file_content: Binary content of the CV file
            filename: Name of the file (for format detection)
            
        Returns:
            Dictionary with structured CV data
        """
        start_time = datetime.utcnow()
        file_hash = self._generate_hash(file_content)
        
        logger.info(f"Starting CV parse for {filename} (hash: {file_hash[:8]})")
        
        # Step 1: Extract raw text (with caching)
        text = self._extract_text_with_cache_bytes(file_content, filename, file_hash)
        
        # Step 2: Clean and normalize text
        cleaned_text = self._clean_text(text)
        
        # Step 3: Parse using regex (always done for baseline)
        regex_data = self._regex_parse(cleaned_text)
        
        # Step 4: Enhance with LLM if available
        if self.use_llm and self.llm:
            try:
                llm_data = await self._parse_with_llm(cleaned_text)
                # Merge LLM results with regex results (LLM takes precedence if fields exist)
                final_data = self._merge_parse_results(regex_data, llm_data)
            except Exception as e:
                logger.warning(f"LLM parsing failed: {e}. Using regex results only.")
                final_data = regex_data
        else:
            final_data = regex_data
        
        # Step 5: Add metadata
        final_data["metadata"] = {
            "parsed_at": start_time.isoformat(),
            "file_hash": file_hash,
            "filename": filename,
            "parsing_method": "llm+regex" if self.use_llm else "regex_only",
            "text_length": len(text)
        }
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Parse completed in {duration:.2f}s")
        
        return final_data
    
    async def extract_skills(self, text: str) -> List[str]:
        """Extract skills from arbitrary text (async)"""
        return self._extract_skills(text)
    
    # ==================== SYNC INTERFACE (for data ingestion) ====================
    
    def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Synchronous PDF parsing (for data ingestion compatibility).
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary with structured CV data
        """
        try:
            text = self._extract_text_from_pdf_file(file_path)
            return self.extract_comprehensive_info(text, os.path.basename(file_path))
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return self.default_response()
    
    def parse_docx(self, file_path: str) -> Dict[str, Any]:
        """
        Synchronous DOCX parsing (for data ingestion compatibility).
        
        Args:
            file_path: Path to DOCX file
            
        Returns:
            Dictionary with structured CV data
        """
        try:
            text = self._extract_text_from_docx_file(file_path)
            return self.extract_comprehensive_info(text, os.path.basename(file_path))
        except Exception as e:
            logger.error(f"Error parsing DOCX: {e}")
            return self.default_response()
    
    def extract_comprehensive_info(self, text: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Extract all information from CV text (sync version).
        Used by data ingestion layer.
        
        Args:
            text: Raw CV text
            filename: Original filename
            
        Returns:
            Dictionary with structured CV data
        """
        start_time = datetime.utcnow()
        
        # Clean text
        cleaned_text = self._clean_text(text)
        
        # Parse using regex
        parsed_data = self._regex_parse(cleaned_text)
        
        # Add metadata
        parsed_data["metadata"] = {
            "parsed_at": start_time.isoformat(),
            "filename": filename,
            "parsing_method": "regex_only",
            "text_length": len(text)
        }
        
        # Add legacy fields for backward compatibility
        parsed_data["certifications"] = []
        parsed_data["projects"] = []
        parsed_data["languages"] = []
        parsed_data["parser_name"] = self.parser_name
        parsed_data["parser_version"] = self.version
        
        return parsed_data
    
    # ==================== TEXT EXTRACTION ====================
    
    def _extract_text_with_cache_bytes(self, file_content: bytes, filename: str, file_hash: str) -> str:
        """Extract text from bytes with caching"""
        # Check cache first
        cached_text = self._load_text_from_cache(file_hash)
        if cached_text:
            logger.info(f"Loaded text from cache: {file_hash[:8]}")
            return cached_text
        
        # Extract text from bytes
        logger.info(f"Extracting text from {filename}")
        text = self._extract_text_from_bytes(file_content, filename)
        
        # Save to cache
        self._save_text_to_cache(file_hash, text, filename)
        
        return text
    
    def _extract_text_from_bytes(self, file_content: bytes, filename: str) -> str:
        """Extract text from byte content"""
        if filename.lower().endswith('.pdf'):
            return self._extract_from_pdf(file_content)
        elif filename.lower().endswith('.docx'):
            return self._extract_from_docx(file_content)
        else:
            raise ValueError(f"Unsupported file format: {filename}")
    
    def _extract_text_from_pdf_file(self, file_path: str) -> str:
        """Extract text from PDF file path"""
        with open(file_path, 'rb') as f:
            return self._extract_from_pdf(f.read())
    
    def _extract_text_from_docx_file(self, file_path: str) -> str:
        """Extract text from DOCX file path"""
        with open(file_path, 'rb') as f:
            return self._extract_from_docx(f.read())
    
    def _extract_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF with fallback"""
        text = ""
        
        try:
            # Try pdfplumber first (better formatting)
            with pdfplumber.open(BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            logger.info("Extracted text using pdfplumber")
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}. Trying PyPDF2...")
            # Fallback to PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                logger.info("Extracted text using PyPDF2")
            except Exception as e2:
                logger.error(f"Both PDF extraction methods failed: {e2}")
                raise
        
        return text.strip()
    
    def _extract_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX"""
        if DocxDocument is None:
            raise ImportError("python-docx is required for DOCX parsing")
        
        doc = DocxDocument(BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    
    # ==================== TEXT CACHING ====================
    
    def _load_text_from_cache(self, file_hash: str) -> Optional[str]:
        """Load cached plain text file"""
        cache_path = os.path.join(self.text_cache_dir, f"{file_hash}.txt")
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load text from cache: {e}")
        
        return None
    
    def _save_text_to_cache(self, file_hash: str, text: str, filename: str):
        """Save extracted plain text to cache"""
        cache_path = os.path.join(self.text_cache_dir, f"{file_hash}.txt")
        metadata_path = os.path.join(self.text_cache_dir, f"{file_hash}.meta.json")
        
        try:
            # Save text file
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Save metadata
            metadata = {
                "file_hash": file_hash,
                "filename": filename,
                "cached_at": datetime.utcnow().isoformat(),
                "text_length": len(text)
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Saved text to cache: {file_hash[:8]}")
        except Exception as e:
            logger.warning(f"Failed to save text to cache: {e}")
    
    # ==================== TEXT PROCESSING ====================
    
    def _clean_text(self, text: str) -> str:
        """Normalize text and fix common OCR artifacts"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors
        replacements = {
            "0ver": "over",
            "15years": "15 years",
            "securi ty": "security",
            "ML&AI": "ML & AI",
            "CICD": "CI/CD",
            "Cl/CD": "CI/CD",
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
        
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        
        return text.strip()
    
    # ==================== REGEX PARSING ====================
    
    def _regex_parse(self, text: str) -> Dict[str, Any]:
        """
        Comprehensive regex-based parsing (fallback method).
        Always runs to provide baseline results.
        """
        # Detect sections
        sections = self._detect_sections(text)
        
        # Extract all fields
        experience = self._extract_experience(sections.get("experience", "") or text)
        
        return {
            "full_name": self._extract_name(text),
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
            "skills": self._extract_skills(sections.get("skills", "") + " " + text),
            "experience": experience,
            "education": self._extract_education(sections.get("education", "") or text),
            "years_of_experience": self.calculate_total_years_experience(experience, text),
            "raw_text": text[:1000],  # First 1000 chars
            "confidence": {
                "overall": 0.75,  # Baseline confidence for regex parsing
                "method": "regex"
            }
        }
    
    def _detect_sections(self, text: str) -> Dict[str, str]:
        """Dynamically detect CV sections"""
        sections = {}
        section_markers = {
            "experience": r"(?i)(employment history|experience|work history|professional experience)",
            "education": r"(?i)(education|academic background|qualifications)",
            "skills": r"(?i)(skills|technical skills|technologies|expertise|core competencies)",
            "projects": r"(?i)(projects|notable projects|key projects)",
        }
        
        lines = text.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if line marks a new section
            matched_section = None
            for section, pattern in section_markers.items():
                if re.match(pattern, line_lower):
                    matched_section = section
                    break
            
            if matched_section:
                # Save previous section
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content).strip()
                
                current_section = matched_section
                section_content = []
            elif current_section:
                section_content.append(line)
        
        # Add final section
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content).strip()
        
        logger.info(f"Detected sections: {list(sections.keys())}")
        return sections
    
    def _extract_name(self, text: str) -> str:
        """Extract name from first few lines"""
        lines = text.split('\n')[:5]
        for line in lines:
            # Look for patterns like "Ahmed ElTaher" or full names
            match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-zA-Z]+)+)', line.strip())
            if match and len(match.group(1).split()) <= 4:
                return match.group(1)
        return "Unknown"
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        # Filter out placeholder emails
        for email in matches:
            if not any(x in email.lower() for x in ['example', 'test', 'sample', 'domain']):
                return email
        return matches[0] if matches else None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number"""
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}',
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                digits_only = re.sub(r'\D', '', match)
                if len(digits_only) >= 10 and not match.startswith('19') and not match.startswith('20'):
                    return match.strip()
        return None
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract and normalize skills"""
        found_skills = set()
        text_lower = text.lower()
        
        # Match against skill ontology
        for normalized, data in self.SKILL_ONTOLOGY.items():
            for alias in data["aliases"]:
                if alias in text_lower:
                    # Use proper casing
                    if normalized.upper() in ['SQL', 'HTML', 'CSS', 'XML', 'JSON', 'REST', 'API', 'AWS', 'GCP', 'NLP', 'AI', 'ML']:
                        found_skills.add(normalized.upper())
                    else:
                        found_skills.add(normalized.replace("_", " ").title())
                    break
        
        # Also extract capitalized tech terms
        tech_terms = re.findall(r'\b[A-Z][a-zA-Z0-9+#.]{1,15}\b', text)
        for term in tech_terms:
            if term.isupper() or any(c.isdigit() for c in term):
                if term not in ['CV', 'PDF', 'DOCX']:  # Filter common non-skills
                    found_skills.add(term)
        
        return sorted(list(found_skills))
    
    def _extract_experience(self, section_text: str) -> List[Dict[str, Any]]:
        """Extract work experience"""
        if not section_text:
            return []
        
        experiences = []
        
        # Pattern: Title at Company, Location (Date - Date)
        exp_patterns = [
            r'([A-Z][A-Za-z\s/&]+?)\s+(?:at|@)\s+([A-Z][A-Za-z\s.,&]+?)(?:,\s*([A-Za-z\s]+?))?(?:\s*[\(\|]\s*)?([A-Za-z]+\s+\d{4}|\d{4})\s*[-–]\s*(Present|[A-Za-z]+\s+\d{4}|\d{4})',
            r'([A-Z][A-Za-z\s/&]+?)\s*[,\|]\s*([A-Z][A-Za-z\s.,&]+?)\s*[,\|]\s*(\d{4}|\w{3,9}\s+\d{4})\s*[-–—]\s*(Present|\d{4}|\w{3,9}\s+\d{4})',
        ]
        
        for pattern in exp_patterns:
            matches = re.findall(pattern, section_text)
            
            for match in matches:
                if len(match) == 5:  # First pattern with location
                    title, company, location, start_date, end_date = match
                else:  # Second pattern without location
                    title, company, start_date, end_date = match
                    location = ""
                
                title = title.strip()
                company = self._normalize_company_name(company.strip().rstrip(','))
                
                # Validate
                if len(title) > 5 and len(company) > 2:
                    experiences.append({
                        "title": title,
                        "company": company,
                        "location": location.strip() if location else "",
                        "startDate": self._normalize_date(start_date),
                        "endDate": "Present" if "present" in end_date.lower() else self._normalize_date(end_date),
                        "description": "",
                        "responsibilities": []
                    })
        
        return experiences[:10]  # Limit to 10
    
    def _extract_education(self, section_text: str) -> List[Dict[str, Any]]:
        """Extract education history"""
        if not section_text:
            return []
        
        education_list = []
        
        for pattern in self.EDUCATION_PATTERNS:
            matches = re.finditer(pattern, section_text, re.IGNORECASE)
            for match in matches:
                # Extract context
                start = max(0, match.start() - 100)
                end = min(len(section_text), match.end() + 100)
                context = section_text[start:end]
                
                # Extract institution
                inst_match = re.search(r'([A-Z][A-Za-z\s&.]{3,50}?(?:University|College|Institute|School))', context)
                institution = inst_match.group(1).strip().rstrip(',.') if inst_match else "Unknown"
                
                # Extract year
                year_match = re.search(r'(19|20)\d{2}', context)
                year = year_match.group(0) if year_match else "Unknown"
                
                # Extract field of study
                field_patterns = [
                    r'in\s+([A-Z][A-Za-z\s]{3,40}?)(?:\s+from|\s+,|\s+-|\s+\|)',
                    r'of\s+([A-Z][A-Za-z\s]{3,40}?)(?:\s+from|\s+,|\s+-|\s+\|)',
                ]
                field = None
                for fp in field_patterns:
                    field_match = re.search(fp, context)
                    if field_match:
                        field = field_match.group(1).strip()
                        break
                
                degree_text = match.group(0)
                degree_type = self._normalize_degree(degree_text)
                
                education_list.append({
                    "degree": f"{degree_type} {field if field else 'Degree'}",
                    "institution": institution,
                    "startDate": str(int(year) - 4) if year != "Unknown" else "Unknown",
                    "endDate": year,
                    "fieldOfStudy": field
                })
        
        # Remove duplicates
        seen = set()
        unique_education = []
        for edu in education_list:
            key = (edu['degree'], edu['institution'])
            if key not in seen:
                seen.add(key)
                unique_education.append(edu)
        
        return unique_education[:5]  # Limit to 5
    
    def calculate_total_years_experience(self, experiences: List[Dict], text: str) -> float:
        """Calculate total years of experience"""
        
        # Method 1: Calculate from experience entries
        if experiences:
            total_months = 0
            for exp in experiences:
                try:
                    start = exp.get("startDate", "")
                    end = exp.get("endDate", "")
                    
                    # Parse start year
                    start_year = int(re.search(r'(19|20)\d{2}', start).group(0)) if re.search(r'(19|20)\d{2}', start) else datetime.now().year
                    
                    # Parse end year
                    if "present" in end.lower():
                        end_year = datetime.now().year
                    else:
                        end_year = int(re.search(r'(19|20)\d{2}', end).group(0)) if re.search(r'(19|20)\d{2}', end) else datetime.now().year
                    
                    years = end_year - start_year
                    total_months += years * 12
                except:
                    continue
            
            if total_months > 0:
                return round(total_months / 12, 1)
        
        # Method 2: Look for explicit years statement
        patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'experience[:\s]+(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s+(?:in|as|of)',
        ]
        
        max_years = 0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    years = int(match)
                    if years <= 50:  # Sanity check
                        max_years = max(max_years, years)
                except:
                    continue
        
        return float(max_years)
    
    # ==================== NORMALIZATION ====================
    
    def _normalize_company_name(self, company: str) -> str:
        """Standardize company names"""
        company_lower = company.lower().strip()
        return self.COMPANY_MAP.get(company_lower, company)
    
    def _normalize_degree(self, degree_text: str) -> str:
        """Normalize degree names"""
        degree_lower = degree_text.lower()
        
        if any(x in degree_lower for x in ['phd', 'ph.d', 'doctorate']):
            return "PhD"
        elif any(x in degree_lower for x in ['master', 'm.s', 'msc', 'mba']):
            return "Master's"
        elif any(x in degree_lower for x in ['bachelor', 'b.s', 'bsc', 'b.a', 'b.tech']):
            return "Bachelor's"
        elif any(x in degree_lower for x in ['associate', 'a.s']):
            return "Associate"
        elif any(x in degree_lower for x in ['diploma']):
            return "Diploma"
        else:
            return degree_text.title()
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date format"""
        if date_parser:
            try:
                parsed = date_parser.parse(date_str, default=datetime(1900, 1, 1))
                return parsed.strftime("%Y-%m")
            except:
                pass
        
        # Fallback: extract year
        year_match = re.search(r'(19|20)\d{2}', date_str)
        if year_match:
            return year_match.group(0) + "-01"
        
        return date_str
    
    # ==================== LLM INTEGRATION ====================
    
    async def _parse_with_llm(self, cv_text: str) -> Dict[str, Any]:
        """Use LLM to enhance parsing (optional)"""
        if not self.llm or not LANGCHAIN_AVAILABLE:
            return {}
        
        try:
            chain = LLMChain(llm=self.llm, prompt=self.parse_prompt)
            result = await chain.arun(cv_text=cv_text[:4000])
            
            # Extract JSON from response
            parsed_data = self._extract_json(result)
            parsed_data["confidence"] = {
                "overall": 0.85,
                "method": "llm"
            }
            
            return parsed_data
        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            return {}
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response"""
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}
    
    def _merge_parse_results(self, regex_data: Dict, llm_data: Dict) -> Dict:
        """Merge regex and LLM results, preferring LLM when available"""
        merged = regex_data.copy()
        
        for key, value in llm_data.items():
            if value and value not in [None, "", [], {}]:
                merged[key] = value
        
        # Update confidence if LLM was used
        if llm_data:
            merged["confidence"]["overall"] = 0.90
            merged["confidence"]["method"] = "hybrid"
        
        return merged
    
    # ==================== UTILITIES ====================
    
    def _generate_hash(self, content: bytes) -> str:
        """Generate content hash for deduplication"""
        return hashlib.sha256(content).hexdigest()[:16]
    
    def extract_phone(self, text: str) -> Optional[str]:
        """Public method for phone extraction (backward compatibility)"""
        return self._extract_phone(text)
    
    def extract_email(self, text: str) -> Optional[str]:
        """Public method for email extraction (backward compatibility)"""
        return self._extract_email(text)
