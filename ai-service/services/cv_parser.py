import os
import json
import re
from typing import Dict, List, Any
from io import BytesIO
import PyPDF2
import pdfplumber
from docx import Document
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


class CVParser:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("MODEL_NAME", "qwen2.5:7b")
        
        # Initialize Ollama LLM
        self.llm = Ollama(
            base_url=self.ollama_url,
            model=self.model_name,
            temperature=0.1
        )
        
        # Prompt templates
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
        
        self.skills_prompt = PromptTemplate(
            input_variables=["text"],
            template="""
Extract all technical skills, programming languages, frameworks, tools, and relevant soft skills from the following text.
Return only a JSON array of skills.

Text:
{text}

Return ONLY a JSON array like: ["skill1", "skill2", "skill3"]
"""
        )
    
    async def parse_cv(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Parse CV file and extract structured information"""
        
        # Extract text from file
        text = self._extract_text(file_content, filename)
        
        # Use LLM to parse CV
        parsed_data = await self._parse_with_llm(text)
        
        return parsed_data
    
    def _extract_text(self, file_content: bytes, filename: str) -> str:
        """Extract text from PDF or DOCX file"""
        
        if filename.lower().endswith('.pdf'):
            return self._extract_from_pdf(file_content)
        elif filename.lower().endswith('.docx'):
            return self._extract_from_docx(file_content)
        else:
            raise ValueError("Unsupported file format")
    
    def _extract_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF"""
        text = ""
        
        try:
            # Try pdfplumber first (better formatting)
            with pdfplumber.open(BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except:
            # Fallback to PyPDF2
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        
        return text.strip()
    
    def _extract_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX"""
        doc = Document(BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    
    async def _parse_with_llm(self, cv_text: str) -> Dict[str, Any]:
        """Use LLM to parse CV text into structured format"""
        
        try:
            chain = LLMChain(llm=self.llm, prompt=self.parse_prompt)
            result = await chain.arun(cv_text=cv_text[:4000])  # Limit text length
            
            # Try to extract JSON from response
            parsed_data = self._extract_json(result)
            
            # Validate and set defaults
            return {
                "full_name": parsed_data.get("full_name", ""),
                "email": parsed_data.get("email", ""),
                "phone": parsed_data.get("phone", ""),
                "skills": parsed_data.get("skills", []),
                "experience": parsed_data.get("experience", []),
                "education": parsed_data.get("education", []),
                "raw_text": cv_text[:1000]  # Store first 1000 chars
            }
        except Exception as e:
            print(f"Error parsing with LLM: {e}")
            # Return basic parsing using regex as fallback
            return self._fallback_parse(cv_text)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response"""
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return {}
    
    def _fallback_parse(self, cv_text: str) -> Dict[str, Any]:
        """Fallback parsing using regex when LLM fails"""
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, cv_text)
        email = emails[0] if emails else ""
        
        # Extract phone
        phone_pattern = r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]'
        phones = re.findall(phone_pattern, cv_text)
        phone = phones[0] if phones else ""
        
        # Extract skills (common technical skills)
        common_skills = [
            'Python', 'JavaScript', 'Java', 'C++', 'React', 'Node.js',
            'SQL', 'MongoDB', 'AWS', 'Docker', 'Kubernetes', 'Git',
            'TypeScript', 'Angular', 'Vue', 'Django', 'Flask', 'FastAPI'
        ]
        skills = [skill for skill in common_skills if skill.lower() in cv_text.lower()]
        
        return {
            "full_name": "",
            "email": email,
            "phone": phone,
            "skills": skills,
            "experience": [],
            "education": [],
            "raw_text": cv_text[:1000]
        }
    
    async def extract_skills(self, text: str) -> List[str]:
        """Extract skills from text using LLM"""
        
        try:
            chain = LLMChain(llm=self.llm, prompt=self.skills_prompt)
            result = await chain.arun(text=text[:2000])
            
            # Parse JSON array
            skills_match = re.search(r'\[.*\]', result, re.DOTALL)
            if skills_match:
                skills = json.loads(skills_match.group())
                return skills
            
            return []
        except Exception as e:
            print(f"Error extracting skills: {e}")
            return []
