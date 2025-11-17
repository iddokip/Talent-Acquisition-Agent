import PyPDF2
import re
from typing import Dict, List, Any

class SimpleCVParser:
    """Simple CV parser that extracts basic information from PDF files"""
    
    # Common skill keywords to look for
    SKILL_KEYWORDS = {
        'programming': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'php', 'swift', 'kotlin', 'go', 'rust'],
        'web': ['react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring', 'express', 'next.js'],
        'mobile': ['ios', 'android', 'react native', 'flutter', 'swift', 'kotlin', 'objective-c'],
        'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle'],
        'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform'],
        'ai_ml': ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn', 'nlp'],
        'tools': ['git', 'jenkins', 'jira', 'agile', 'scrum', 'ci/cd']
    }
    
    def parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text and information from PDF"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
            
            return self.extract_info(text)
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            return self.default_response()
    
    def extract_info(self, text: str) -> Dict[str, Any]:
        """Extract structured information from text"""
        text_lower = text.lower()
        
        # Extract skills
        skills = self.extract_skills(text_lower)
        
        # Extract years of experience
        years_exp = self.extract_years_of_experience(text)
        
        # Extract phone
        phone = self.extract_phone(text)
        
        # Extract email
        email = self.extract_email(text_lower)
        
        return {
            "skills": skills,
            "experience": [],
            "education": [],
            "phone": phone,
            "email": email,
            "years_of_experience": years_exp
        }
    
    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from text"""
        found_skills = []
        
        for category, skills in self.SKILL_KEYWORDS.items():
            for skill in skills:
                if skill.lower() in text:
                    # Capitalize properly
                    found_skills.append(skill.title() if len(skill) > 3 else skill.upper())
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(found_skills))
    
    def extract_years_of_experience(self, text: str) -> float:
        """Extract years of experience from text"""
        # Look for patterns like "5 years", "5+ years", "5-7 years"
        patterns = [
            r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
            r'experience:\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*years?\s+(?:in|as)',
        ]
        
        max_years = 0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    years = int(match)
                    max_years = max(max_years, years)
                except:
                    continue
        
        return float(max_years)
    
    def extract_phone(self, text: str) -> str:
        """Extract phone number from text"""
        # Look for phone patterns
        phone_patterns = [
            r'\+?[\d\s\-\(\)]{10,}',
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        
        return None
    
    def extract_email(self, text: str) -> str:
        """Extract email from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group(0) if match else None
    
    def default_response(self) -> Dict[str, Any]:
        """Return default empty response"""
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "phone": None,
            "email": None,
            "years_of_experience": 0
        }
