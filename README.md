# RepoLens

A RAG-powered wiki generator for public GitHub repositories. Enter a repo URL and RepoLens automatically generates comprehensive wiki pages and enables a chat interface for asking questions about the codebase.

## Features

- **Automatic wiki generation** — structured pages with navigation, generated from actual source code
- **Multi-turn chat Q&A** — ask questions about any repo with persistent conversation memory and source attribution
- **Deep research mode** — multi-step analysis (planner + update + synthesizer) for complex architectural questions
- **Hybrid retrieval** — three retrieval modes: dense-only, hybrid (dense + BM25 with RRF), and hybrid + cross-encoder reranking
- **Eval pipeline** — synthetic question generation + LLM-as-judge scoring (relevance, groundedness, retrieval relevance) via LangSmith
- **Multi-language output** — generate wikis in English or Chinese
- **Provider flexibility** — switch between Google Gemini and OpenRouter LLMs; per-request API key overrides via headers
- **API key management** — configure API keys from the frontend UI
- **Wiki caching** — generated wikis are cached in SQLite so they load instantly on revisit
- **Docker support** — multi-stage Dockerfile with Render.com deployment config

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (TypeScript, React 19), Tailwind CSS v4 |
| Backend | FastAPI (Python 3.13+) |
| RAG Engine | LangGraph + LangChain |
| LLMs | Google Gemini (2.0 Flash, 2.5 Flash, 1.5 Pro), OpenRouter (GPT-4o, Claude Sonnet 4.5, Llama 3.3, Qwen 2.5, etc.) |
| Embeddings | OpenAI `text-embedding-3-small` / Google `gemini-embedding-001` (configurable) |
| Sparse Search | BM25 via `rank-bm25` |
| Reranking | Cross-encoder via `sentence-transformers` |
| Vector Store | Qdrant (local file mode) |
| Eval | LangSmith + LLM-as-judge evaluators |
| Conversation Memory | LangGraph + SQLite checkpoints |
| Wiki Cache | SQLite |

## Prerequisites

- Python 3.13+
- Node.js 18+
- [`uv`](https://docs.astral.sh/uv/) Python package manager
- OpenAI API key — used by the default embedder (`text-embedding-3-small`)
- Google API key ([get one here](https://aistudio.google.com/app/apikey)) — for Google Gemini LLMs and/or Google embeddings
- OpenRouter API key (optional, for OpenRouter models)
- LangSmith API key (optional, for eval pipeline tracing)

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/your-username/RepoLens.git
cd RepoLens
```

**2. Configure environment variables**
```bash
cp .env.example .env
```
Fill in `.env`:
```
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key
OPENROUTER_API_KEY=your_openrouter_api_key    # optional
LANGSMITH_API_KEY=your_langsmith_api_key      # optional, for eval
LANGSMITH_TRACING=true                        # optional, for eval
```

**3. Install backend dependencies**
```bash
uv sync
```

**4. Install frontend dependencies**
```bash
cd frontend && npm install
```

## Running

Start both servers simultaneously (in separate terminals):

**Backend** (port 8002):
```bash
uv run uvicorn api.api:app --host 0.0.0.0 --port 8002 --reload
```

**Frontend** (port 3000):
```bash
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Docker

Build and run the backend with Docker:

```bash
docker build -t repolens .
docker run -p 8002:8002 \
  -e GOOGLE_API_KEY=... \
  -e OPENAI_API_KEY=... \
  -v ~/.repolens:/root/.repolens \
  repolens
```

## How It Works

### Indexing a Repository

When you submit a GitHub URL, RepoLens:

1. Clones the repo with `--depth 1` (shallow clone, no history)
2. Walks all files, skipping `node_modules`, `.git`, `__pycache__`, etc.
3. Filters large files (> 20,000 tokens for code, > 2,000 tokens for docs)
4. Chunks files using token-aware splitters (350-token chunks / 100-token overlap for code; 200/50 for docs)
5. Embeds chunks via OpenAI `text-embedding-3-small` (default) or Google Generative AI Embeddings
6. Stores in a per-repo Qdrant collection at `~/.repolens/qdrant/`

### Retrieval Modes

RepoLens supports three retrieval strategies:

| Mode | How it works |
|------|-------------|
| **Dense** | Vector similarity search only |
| **Hybrid** | Dense + BM25 sparse search, merged with Reciprocal Rank Fusion (k=60) |
| **Hybrid + Rerank** | Hybrid retrieval → cross-encoder reranking (top-20 candidates narrowed to top-5) |

### Wiki Generation

1. `POST /wiki/structure` — LLM analyzes the file tree and README to plan wiki pages
2. `POST /wiki/generate-page` — each page is generated via RAG (retrieve relevant chunks → format context → generate markdown)
3. Generated wikis are cached in SQLite and reused on subsequent visits

### Chat Q&A

Uses a RAG graph: retrieve → format context → generate. Responses include source attribution (file paths + relevant snippets). Conversation history is persisted per session via LangGraph checkpoints.

### Deep Research

Runs 3 LLM calls: **planner** (iteration 1 — analyzes top-20 retrieved chunks, lays out an investigation strategy, emits a refined search query) → **update** (iteration 2 — re-retrieves using the refined query, digs a new angle) → **synthesizer** (conclude node — combines all accumulated notes into a final answer). Early exit is possible if the update node signals `[RESEARCH_COMPLETE]`.

### Eval Pipeline

Automated RAG quality evaluation:

1. **Dataset generation** — LLM generates synthetic questions across 6 categories: direct, rephrased, conceptual, negative (hallucination tests), cross-file, and keyword (exact identifier questions)
2. **RAG execution** — runs each question through the RAG graph
3. **LLM-as-judge scoring** — three evaluators grade each response:
   - **Relevance** — does the answer address the question?
   - **Groundedness** — is the answer supported by retrieved context?
   - **Retrieval relevance** — did the retriever fetch useful chunks?
4. Results are persisted in SQLite and accessible via API

## Data Persistence

```
~/.repolens/
├── qdrant/          # Vector embeddings per repo
├── checkpoints.db   # Conversation history (LangGraph)
└── wiki_cache.db    # Generated wikis + eval results
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/models/config` | GET | Available LLM providers and models |
| `/lang/config` | GET | Supported output languages |
| `/wiki/structure` | POST | Plan wiki pages for a repo |
| `/wiki/generate-page` | POST | Generate a single wiki page (streaming) |
| `/wiki/cache` | GET/POST/DELETE | Fetch, save, or clear cached wiki |
| `/api/processed_projects` | GET | List all cached wikis |
| `/chat/stream` | POST | Multi-turn RAG chat (streaming) |
| `/chat/deep-research` | POST | Deep research: planner + update + synthesizer (streaming) |
| `/eval/run` | POST | Run eval pipeline for a repo |
| `/eval/results` | GET | Fetch most recent eval results |

## Project Structure

```
RepoLens/
├── api/
│   ├── api.py                  # FastAPI app — all routes
│   ├── data_pipeline.py        # Repo cloning and chunking
│   ├── vectorstore.py          # Qdrant collection management
│   ├── llm.py                  # Multi-provider LLM factory
│   ├── embedder.py             # Embedding provider factory
│   ├── reranker.py             # Cross-encoder reranker
│   ├── prompts.py              # LLM prompt templates
│   ├── wiki_cache.py           # SQLite wiki cache
│   ├── checkpointer.py         # LangGraph conversation memory
│   ├── graphs/                 # LangGraph graph builders
│   │   ├── rag_graph.py        #   RAG chat (dense / hybrid / hybrid+rerank)
│   │   ├── wiki_page_graph.py  #   Wiki page generation
│   │   └── deep_research_graph.py  # Multi-iteration deep research
│   ├── nodes/                  # Individual graph node functions
│   │   ├── retrieve.py         #   Dense, hybrid, and reranked retrieval
│   │   ├── retrieve_wiki.py    #   Wiki-specific retrieval
│   │   ├── format_context.py   #   Group docs by file path
│   │   ├── generate.py         #   LLM answer generation
│   │   ├── generate_page.py    #   LLM wiki page generation
│   │   └── research_nodes.py   #   Plan, update, conclude nodes
│   ├── eval/                   # Eval pipeline
│   │   ├── dataset_gen.py      #   Synthetic question generation
│   │   ├── runner.py           #   Eval orchestration
│   │   ├── evaluators.py       #   LLM-as-judge scorers
│   │   └── eval_cache.py       #   Eval result persistence
│   └── config/                 # LLM provider and embedder config
│       ├── generator.json
│       └── embedder.json
├── frontend/
│   ├── src/app/
│   │   ├── page.tsx            # Home — repo URL input
│   │   └── [owner]/[repo]/
│   │       └── page.tsx        # Wiki viewer
│   ├── src/components/
│   │   ├── Ask.tsx             # Chat sidebar (Fast/Deep mode toggle)
│   │   ├── ApiKeysModal.tsx    # API key management modal
│   │   ├── ConfigCard.tsx      # Provider/model/language selector
│   │   ├── Markdown.tsx        # Markdown + Mermaid renderer
│   │   ├── Navbar.tsx          # Navigation bar
│   │   └── WikiTreeView.tsx    # Sidebar navigation
│   └── src/hooks/
│       └── useStreamingContent.ts  # Streaming response hook
├── Dockerfile                  # Multi-stage Docker build
└── render.yaml                 # Render.com deployment config
```

## Deployment

### Render.com

The included `render.yaml` configures a Docker-based web service with:
- Health check at `/health`
- 10 GB persistent disk at `/root/.repolens` for Qdrant, wiki cache, and checkpoints
- Environment variables for API keys and CORS origins

## License

MIT
