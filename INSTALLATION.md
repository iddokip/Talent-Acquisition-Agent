# Installation Guide - Agentic AI Recruitment System

This guide will walk you through setting up the complete system including Backend (NestJS), AI Service (FastAPI), and Frontend (Next.js).

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Node.js** (v18 or higher)
   ```bash
   node --version  # Should be v18+
   ```

2. **Python** (v3.11 or higher)
   ```bash
   python --version  # Should be 3.11+
   ```

3. **Docker & Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **Ollama** (for local LLM)
   - Download from: https://ollama.ai
   - Install and run Ollama

## Step 1: Clone and Setup Infrastructure

### 1.1 Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, Weaviate, and Elasticsearch
docker-compose up -d

# Verify services are running
docker ps
```

You should see 4 containers running:
- `recruitment_postgres` (PostgreSQL)
- `recruitment_redis` (Redis)
- `recruitment_weaviate` (Weaviate)
- `recruitment_elasticsearch` (Elasticsearch)

### 1.2 Setup Ollama

```bash
# Pull the required models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Verify Ollama is running and models are available
curl http://localhost:11434/api/tags
```

## Step 2: Backend Setup (NestJS)

```bash
# Navigate to backend directory
cd backend

# Copy environment file
cp .env.example .env

# Install dependencies
npm install

# Start the backend in development mode
npm run start:dev
```

The backend should now be running on **http://localhost:3001**

### Backend Endpoints
- API: http://localhost:3001/api
- Swagger Docs: http://localhost:3001/api/docs

## Step 3: AI Service Setup (FastAPI)

```bash
# Navigate to ai-service directory
cd ai-service

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Copy environment file
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Start the AI service
uvicorn main:app --reload --port 8001
```

The AI service should now be running on **http://localhost:8001**

### AI Service Endpoints
- API: http://localhost:8001
- Interactive Docs: http://localhost:8001/docs
- Health Check: http://localhost:8001/health

## Step 4: Frontend Setup (Next.js)

```bash
# Navigate to frontend directory
cd frontend

# Copy environment file
cp .env.local.example .env.local

# Install dependencies
npm install

# Start the frontend in development mode
npm run dev
```

The frontend should now be running on **http://localhost:3000**

## Step 5: Verification

### 5.1 Check All Services

1. **Frontend**: http://localhost:3000 ✅
2. **Backend API**: http://localhost:3001/api/docs ✅
3. **AI Service**: http://localhost:8001/docs ✅
4. **PostgreSQL**: Port 5432 ✅
5. **Redis**: Port 6379 ✅
6. **Weaviate**: http://localhost:8080 ✅
7. **Elasticsearch**: http://localhost:9200 ✅
8. **Ollama**: http://localhost:11434 ✅

### 5.2 Test the System

1. Open http://localhost:3000 in your browser
2. Upload a sample CV (PDF or DOCX)
3. View the parsed candidate information
4. Create a job description and rank candidates

## Environment Configuration

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
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production
JWT_EXPIRATION=24h
PORT=3001
NODE_ENV=development
MAX_FILE_SIZE=10485760
UPLOAD_DIR=./uploads
```

### AI Service (.env)
```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5:7b
EMBEDDING_MODEL=nomic-embed-text
WEAVIATE_URL=http://localhost:8080
PORT=8001
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

## Troubleshooting

### Issue: Backend can't connect to database
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Issue: AI Service can't connect to Ollama
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not running, start Ollama
ollama serve
```

### Issue: Port already in use
```bash
# Find process using port (e.g., 3000)
lsof -ti:3000

# Kill the process
kill -9 <PID>
```

### Issue: CV parsing is slow
- Ollama models can be resource-intensive
- Consider using a smaller model like `phi` or `mistral`
- Or use a GPU-enabled system for faster inference

```bash
ollama pull phi
# Then update MODEL_NAME=phi in ai-service/.env
```

## Production Deployment

For production deployment:

1. **Environment Variables**: Use proper secrets management
2. **Database**: Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
3. **Redis**: Use managed Redis (AWS ElastiCache, Redis Cloud)
4. **Ollama**: Consider using OpenAI API or other cloud LLM providers
5. **Build**: Create production builds
   ```bash
   # Backend
   cd backend && npm run build
   
   # Frontend
   cd frontend && npm run build
   ```

## Stopping Services

```bash
# Stop all Docker containers
docker-compose down

# Stop backend
# Ctrl+C in backend terminal

# Stop AI service
# Ctrl+C in AI service terminal

# Stop frontend
# Ctrl+C in frontend terminal

# Deactivate Python virtual environment
deactivate
```

## Useful Commands

```bash
# View logs
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f weaviate

# Reset database
docker-compose down -v
docker-compose up -d

# Update dependencies
cd backend && npm update
cd ai-service && pip install --upgrade -r requirements.txt
cd frontend && npm update
```

## Support

For issues and questions:
- Check the main [README.md](./README.md)
- Review the requirements document
- Check service logs for error messages

## Next Steps

- Upload sample CVs
- Test candidate ranking
- Customize the scoring algorithm
- Add more features from the requirements document
