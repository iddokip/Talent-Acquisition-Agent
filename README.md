# Agentic AI Recruitment System

## Feature 1: Automated CV Parsing & Ranking

This implementation includes:
- **Backend (NestJS)**: Core API and business logic
- **AI Service (FastAPI)**: CV parsing and ranking using LangChain + Ollama
- **Frontend (Next.js 14)**: Modern UI with React, TypeScript, TailwindCSS, and ShadCN UI
- **Databases**: PostgreSQL (main data), Weaviate (vector search)
- **Infrastructure**: Docker Compose for local development

## Architecture

```
┌─────────────────┐
│   Frontend      │
│   (Next.js)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Backend API    │
│   (NestJS)      │
└────────┬────────┘
         │
         ├──────────┐
         ▼          ▼
┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │  AI Service  │
│              │ │  (FastAPI)   │
└──────────────┘ └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   Weaviate   │
                 │   (Vectors)  │
                 └──────────────┘
```

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Ollama (for local LLM)

### Installation

1. **Install Ollama and pull the required models**:
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

2. **Start infrastructure services**:
```bash
docker-compose up -d
```

3. **Setup Backend (NestJS)**:
```bash
cd backend
npm install
npm run start:dev
```

4. **Setup AI Service (FastAPI)**:
```bash
cd ai-service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

5. **Setup Frontend (Next.js)**:
```bash
cd frontend
npm install
npm run dev
```

### Access Points
- Frontend: http://localhost:3000
- Backend API: http://localhost:3001
- AI Service: http://localhost:8001
- API Docs (FastAPI): http://localhost:8001/docs

## Features Implemented

### 1. CV Upload & Parsing
- Supports PDF and DOCX formats
- Extracts: personal info, skills, experience, education
- Structured data mapping

### 2. AI-Powered Ranking
- Semantic similarity matching with job requirements
- Scoring based on:
  - Skills match (40%)
  - Experience relevance (30%)
  - Education fit (20%)
  - Additional factors (10%)

### 3. Vector Search
- Weaviate integration for semantic CV search
- Fast candidate retrieval based on job descriptions

### 4. Modern UI
- Drag & drop CV upload
- Real-time parsing status
- Candidate ranking dashboard
- Detailed candidate profiles

## Tech Stack

- **Backend**: NestJS, TypeScript, TypeORM, PostgreSQL
- **AI Service**: FastAPI, LangChain, Ollama, Weaviate
- **Frontend**: Next.js 14, React, TypeScript, TailwindCSS, ShadCN UI
- **Databases**: PostgreSQL, Redis, Weaviate
- **Infrastructure**: Docker, Docker Compose

## API Endpoints

### Backend (NestJS)
- `POST /api/candidates/upload` - Upload CV
- `GET /api/candidates` - List all candidates
- `GET /api/candidates/:id` - Get candidate details
- `POST /api/candidates/rank` - Rank candidates for a job

### AI Service (FastAPI)
- `POST /parse-cv` - Parse CV file
- `POST /rank-candidates` - Rank candidates against job description
- `POST /extract-skills` - Extract skills from text

## Environment Variables

Create `.env` files in each service directory:

### Backend (.env)
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=recruitment_db
REDIS_HOST=localhost
REDIS_PORT=6379
AI_SERVICE_URL=http://localhost:8001
JWT_SECRET=your-secret-key
```

### AI Service (.env)
```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5:7b
EMBEDDING_MODEL=nomic-embed-text
WEAVIATE_URL=http://localhost:8080
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

## Database Schema

### Candidates Table
```sql
- id: UUID (primary key)
- email: string (unique)
- full_name: string
- phone: string
- skills: json
- experience: json
- education: json
- cv_file_path: string
- parsed_data: json
- score: float
- created_at: timestamp
- updated_at: timestamp
```

## Development

### Run Tests
```bash
# Backend
cd backend && npm run test

# AI Service
cd ai-service && pytest

# Frontend
cd frontend && npm run test
```

### Code Quality
```bash
# Backend
npm run lint
npm run format

# AI Service
black .
flake8

# Frontend
npm run lint
npm run format
```

## License

MIT
