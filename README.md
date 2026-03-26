# RepoLens

A RAG-powered wiki generator for public GitHub repositories. Enter a repo URL and RepoLens automatically generates comprehensive wiki pages and enables a chat interface for asking questions about the codebase.

## Features

- **Automatic wiki generation** — structured pages with navigation, generated from actual source code
- **Multi-turn chat Q&A** — ask questions about any repo with persistent conversation memory
- **Deep research mode** — multi-step analysis (planner + update + synthesizer) for complex architectural questions
- **Multi-language output** — generate wikis in English or Chinese
- **Provider flexibility** — switch between Google Gemini and OpenRouter LLMs
- **Wiki caching** — generated wikis are cached in SQLite so they load instantly on revisit

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (TypeScript), Tailwind CSS v4 |
| Backend | FastAPI (Python 3.13+) |
| RAG Engine | LangGraph + LangChain |
| LLMs | Google Gemini, OpenRouter |
| Embeddings | OpenAI `text-embedding-3-small` / Google Generative AI Embeddings (configurable) |
| Vector Store | Qdrant (local file mode) |
| Conversation Memory | LangGraph + SQLite checkpoints |
| Wiki Cache | SQLite |

## Prerequisites

- Python 3.13+
- Node.js 18+
- [`uv`](https://docs.astral.sh/uv/) Python package manager
- OpenAI API key — used by the default embedder (`text-embedding-3-small`)
- Google API key ([get one here](https://aistudio.google.com/app/apikey)) — for Google Gemini LLMs and/or Google embeddings
- OpenRouter API key (optional, for OpenRouter models)

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
OPENROUTER_API_KEY=your_openrouter_api_key  # optional
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

## How It Works

### Indexing a Repository

When you submit a GitHub URL, RepoLens:

1. Clones the repo with `--depth 1` (shallow clone, no history)
2. Walks all files, skipping `node_modules`, `.git`, `__pycache__`, etc.
3. Filters large files (> 20,000 tokens for code, > 2,000 tokens for docs)
4. Chunks files using token-aware splitters (350-token chunks / 100-token overlap for code; 200/50 for docs)
5. Embeds chunks via OpenAI `text-embedding-3-small` (default) or Google Generative AI Embeddings
6. Stores in a per-repo Qdrant collection at `~/.deepwiki/qdrant/`

### Wiki Generation

1. `POST /wiki/structure` — LLM analyzes the file tree and README to plan wiki pages
2. `POST /wiki/generate-page` — each page is generated via RAG (retrieve relevant chunks → format context → generate markdown)
3. Generated wikis are cached in SQLite and reused on subsequent visits

### Chat Q&A

Uses a simple RAG graph: retrieve → format context → generate. Conversation history is persisted per session via LangGraph checkpoints.

### Deep Research

Runs 3 LLM calls: **planner** (iteration 1 — analyzes top-20 retrieved chunks, lays out an investigation strategy, emits a refined search query) → **update** (iteration 2 — re-retrieves using the refined query, digs a new angle) → **synthesizer** (conclude node — combines all accumulated notes into a final answer). Early exit is possible if the update node signals `[RESEARCH_COMPLETE]`.

## Data Persistence

```
~/.deepwiki/
├── qdrant/          # Vector embeddings per repo
├── checkpoints.db   # Conversation history (LangGraph)
└── wiki_cache.db    # Generated wikis
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

## Project Structure

```
RepoLens/
├── api/
│   ├── api.py                  # FastAPI app — all routes
│   ├── data_pipeline.py        # Repo cloning and chunking
│   ├── vectorstore.py          # Qdrant collection management
│   ├── prompts.py              # LLM prompt templates
│   ├── wiki_cache.py           # SQLite wiki cache
│   ├── checkpointer.py         # LangGraph conversation memory
│   ├── graphs/                 # LangGraph graph builders
│   │   ├── rag_graph.py
│   │   ├── wiki_page_graph.py
│   │   └── deep_research_graph.py
│   ├── nodes/                  # Individual graph node functions
│   └── config/                 # LLM provider and embedder config
└── frontend/
    ├── src/app/
    │   ├── page.tsx            # Home — repo URL input
    │   └── [owner]/[repo]/
    │       └── page.tsx        # Wiki viewer
    ├── src/components/
    │   ├── Ask.tsx             # Chat sidebar
    │   ├── ConfigCard.tsx      # Provider/model/language selector
    │   ├── Markdown.tsx        # Markdown + Mermaid renderer
    │   └── WikiTreeView.tsx    # Sidebar navigation
    └── src/hooks/
        └── useStreamingContent.ts  # Streaming response hook
```

## License

MIT
