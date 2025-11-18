"""
Advanced CV Parser

Comprehensive CV parser with extensive information extraction capabilities.
Migrated from ai-service/advanced_cv_parser.py into the data ingestion layer.
"""

import PyPDF2
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
try:
    from docx import Document
except ImportError:
    Document = None

from .base_parser import BaseParser


class CVParser(BaseParser):
    """Comprehensive CV parser with extensive information extraction capabilities"""
    
    # Expanded skill keywords
    SKILL_KEYWORDS = {
        'programming': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin', 'go', 'rust', 'scala', 'r', 'matlab'],
        'web': ['react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring', 'express', 'next.js', 'nuxt', 'svelte', 'fastapi', 'asp.net'],
        'mobile': ['ios', 'android', 'react native', 'flutter', 'swift', 'kotlin', 'objective-c', 'xamarin', 'ionic'],
        'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 'cassandra', 'dynamodb', 'neo4j'],
        'cloud': ['aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'terraform', 'cloudformation', 'openshift'],
        'ai_ml': ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn', 'nlp', 'computer vision', 'keras', 'pandas', 'numpy'],
        'tools': ['git', 'jenkins', 'jira', 'agile', 'scrum', 'ci/cd', 'github', 'gitlab', 'bitbucket', 'confluence'],
        'testing': ['junit', 'pytest', 'selenium', 'jest', 'mocha', 'cypress', 'testng'],
        'devops': ['linux', 'bash', 'ansible', 'puppet', 'chef', 'nginx', 'apache']
    }
    
    # Education degree patterns
    EDUCATION_PATTERNS = [
        r'(phd|ph\.d\.|doctorate|doctoral)',
        r'(master|m\.s\.|msc|m\.sc\.|mba|m\.b\.a\.)',
        r'(bachelor|b\.s\.|bsc|b\.sc\.|b\.a\.|ba|b\.tech|b\.e\.)',
        r'(associate|a\.s\.|diploma)',
    ]
    
    def __init__(self):
        """Initialize the advanced CV parser"""
        super().__init__()
        self.version = "2.0.0"
    
    def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract comprehensive information from PDF"""
        try:
            text = self._extract_text_from_pdf(file_path)
            return self.extract_comprehensive_info(text)
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            return self.default_response()
    
    def parse_docx(self, file_path: str) -> Dict[str, Any]:
        """Extract comprehensive information from DOCX"""
        try:
            text = self._extract_text_from_docx(file_path)
            return self.extract_comprehensive_info(text)
        except Exception as e:
            print(f"Error parsing DOCX: {e}")
            return self.default_response()
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if Document is None:
            raise ImportError("python-docx is required for DOCX parsing")
        
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    
    def extract_comprehensive_info(self, text: str) -> Dict[str, Any]:
        """Extract all information from CV text"""
        text_lower = text.lower()
        
        # Extract components
        skills = self.extract_skills(text_lower, text)
        experience = self.extract_experience(text)
        education = self.extract_education(text)
        years_exp = self.calculate_total_years_experience(experience, text)
        phone = self.extract_phone(text)
        email = self.extract_email(text_lower)
        
        return {
            "skills": skills,
            "experience": experience,
            "education": education,
            "phone": phone,
            "email": email,
            "years_of_experience": years_exp,
            "certifications": [],
            "projects": [],
            "languages": [],
            "parser_name": self.parser_name,
            "parser_version": self.version,
            "raw_text": text[:1000]  # Store first 1000 chars for reference
        }
    
    def extract_skills(self, text_lower: str, original_text: str) -> List[str]:
        """Extract skills with better accuracy"""
        found_skills = set()
        
        # Method 1: Keyword matching from predefined list
        for category, skills in self.SKILL_KEYWORDS.items():
            for skill in skills:
                if skill.lower() in text_lower:
                    # Use original casing when possible
                    found_skills.add(self._normalize_skill_name(skill, original_text))
        
        # Method 2: Extract from "Skills" section
        skills_section = self._extract_section(original_text, ['skills', 'technical skills', 'core competencies'])
        if skills_section:
            # Extract comma-separated or bullet-pointed skills
            skill_patterns = [
                r'(?:^|\n|•|\*|-)\s*([A-Z][A-Za-z0-9\+\#\./\s]{2,30})(?:\n|,|•|\*|-|$)',
            ]
            for pattern in skill_patterns:
                matches = re.findall(pattern, skills_section, re.MULTILINE)
                for match in matches:
                    skill = match.strip()
                    if len(skill) > 2 and not skill.startswith(('Experience', 'Education', 'Project')):
                        found_skills.add(skill)
        
        return sorted(list(found_skills))
    
    def extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Extract work experience with dates"""
        experiences = []
        
        # Try to find experience section
        exp_section = self._extract_section(text, ['experience', 'work experience', 'employment history', 'professional experience'])
        
        if not exp_section:
            # Try to find experience entries anywhere in text
            exp_section = text
        
        # Pattern: Job Title at Company (Date - Date)
        patterns = [
            # Pattern 1: Title at Company (Date - Date)
            r'([A-Z][A-Za-z\s]{2,40}?)\s+(?:at|@)\s+([A-Z][A-Za-z\s&.,]{2,40}?)\s*[\(\|]?\s*(\d{4}|\w{3,9}\s+\d{4})\s*[-–—]\s*(Present|\d{4}|\w{3,9}\s+\d{4})',
            # Pattern 2: Title, Company, Date-Date
            r'([A-Z][A-Za-z\s]{2,40}?)\s*[,\|]\s*([A-Z][A-Za-z\s&.,]{2,40}?)\s*[,\|]\s*(\d{4}|\w{3,9}\s+\d{4})\s*[-–—]\s*(Present|\d{4}|\w{3,9}\s+\d{4})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, exp_section, re.MULTILINE)
            for match in matches:
                title, company, start_date, end_date = match
                
                # Clean up extracted data
                title = title.strip()
                company = company.strip().rstrip(',.')
                
                # Validate
                if len(title) > 5 and len(company) > 2:
                    experiences.append({
                        "title": title,
                        "company": company,
                        "startDate": self._normalize_date(start_date),
                        "endDate": "Present" if "present" in end_date.lower() else self._normalize_date(end_date),
                        "description": "",
                        "responsibilities": []
                    })
        
        return experiences[:10]  # Limit to 10 most relevant
    
    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extract education credentials"""
        education_list = []
        
        # Try to find education section
        edu_section = self._extract_section(text, ['education', 'academic background', 'qualifications', 'academic qualifications'])
        
        if not edu_section:
            edu_section = text
        
        # Pattern: Degree in Field from Institution (Date)
        for pattern in self.EDUCATION_PATTERNS:
            matches = re.finditer(pattern, edu_section, re.IGNORECASE)
            for match in matches:
                # Extract context around the match
                start = max(0, match.start() - 100)
                end = min(len(edu_section), match.end() + 100)
                context = edu_section[start:end]
                
                # Try to extract institution
                institution = self._extract_institution(context)
                
                # Try to extract year
                year_match = re.search(r'(19|20)\d{2}', context)
                year = year_match.group(0) if year_match else "Unknown"
                
                # Try to extract field of study
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
                    "institution": institution or "Unknown",
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
        
        return unique_education[:5]  # Limit to 5 most relevant
    
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
        
        # Method 2: Look for explicit years of experience statement
        patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'experience[:\s]+(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s+(?:in|as|of)',
            r'total\s+experience[:\s]+(\d+)\+?\s*years?',
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
    
    def _extract_section(self, text: str, section_names: List[str]) -> Optional[str]:
        """Extract a specific section from CV"""
        for section_name in section_names:
            # Try to find section header
            pattern = rf'\b{section_name}\b[:\s]*\n(.*?)(?=\n[A-Z][A-Za-z\s]{{3,30}}[:\n]|\Z)'
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
        return None
    
    def _extract_institution(self, context: str) -> Optional[str]:
        """Extract educational institution from context"""
        # Common university/college patterns
        patterns = [
            r'(?:from|at)\s+([A-Z][A-Za-z\s&.]{3,50}?(?:University|College|Institute|School))',
            r'([A-Z][A-Za-z\s&.]{3,50}?(?:University|College|Institute|School))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, context)
            if match:
                institution = match.group(1).strip().rstrip(',.-')
                if len(institution) > 5:
                    return institution
        
        return None
    
    def _normalize_degree(self, degree_text: str) -> str:
        """Normalize degree names"""
        degree_lower = degree_text.lower()
        
        if any(x in degree_lower for x in ['phd', 'ph.d', 'doctorate', 'doctoral']):
            return "PhD"
        elif any(x in degree_lower for x in ['master', 'm.s', 'msc', 'm.sc', 'mba', 'm.b.a']):
            return "Master's"
        elif any(x in degree_lower for x in ['bachelor', 'b.s', 'bsc', 'b.sc', 'b.a', 'b.tech', 'b.e']):
            return "Bachelor's"
        elif any(x in degree_lower for x in ['associate', 'a.s']):
            return "Associate"
        elif any(x in degree_lower for x in ['diploma', 'certificate']):
            return "Diploma"
        else:
            return "Degree"
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date format"""
        # Extract year if present
        year_match = re.search(r'(19|20)\d{2}', date_str)
        if year_match:
            year = year_match.group(0)
            # Try to extract month
            month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', date_str, re.IGNORECASE)
            if month_match:
                return f"{month_match.group(0)[:3]} {year}"
            return year
        return date_str
    
    def _normalize_skill_name(self, skill: str, text: str) -> str:
        """Normalize skill name with proper casing"""
        # Check if skill appears in original text with specific casing
        pattern = re.compile(re.escape(skill), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(0)
        
        # Default normalization
        if skill.lower() in ['sql', 'html', 'css', 'xml', 'json', 'rest', 'api', 'aws', 'gcp', 'nlp', 'ai', 'ml', 'ci', 'cd']:
            return skill.upper()
        elif '.' in skill:
            return skill.title()
        else:
            return skill.capitalize()
    
    def extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number with better accuracy"""
        # Improved phone patterns
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}',  # International format
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (123) 456-7890
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # 123-456-7890
            r'\d{10}',  # 1234567890
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Validate it's not a year or other number
                digits_only = re.sub(r'\D', '', match)
                if len(digits_only) >= 10 and not match.startswith('19') and not match.startswith('20'):
                    return match.strip()
        
        return None
    
    def extract_email(self, text: str) -> Optional[str]:
        """Extract email with better pattern"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        # Return first valid email that doesn't look like a placeholder
        for email in matches:
            if not any(x in email.lower() for x in ['example', 'test', 'sample', 'domain']):
                return email
        return matches[0] if matches else None
