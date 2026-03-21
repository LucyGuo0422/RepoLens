"""
Data pipeline: clone a public GitHub repo, chunk its files, and return LangChain Documents.
"""
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Literal, Tuple

import git
import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent / "config" / "embedder.json"
with open(_CONFIG_PATH) as _f:
    _CFG = json.load(_f)

CHUNK_SIZE_CODE: int = _CFG["chunk_size_code"]
CHUNK_OVERLAP_CODE: int = _CFG["chunk_overlap_code"]
CHUNK_SIZE_DOC: int = _CFG["chunk_size_doc"]
CHUNK_OVERLAP_DOC: int = _CFG["chunk_overlap_doc"]
MAX_TOKENS_CODE: int = _CFG["max_tokens_code"]
MAX_TOKENS_DOC: int = _CFG["max_tokens_doc"]

# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------
_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".idea", ".vscode",
    "vendor", "bower_components", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "target", "out", ".output", ".nuxt", ".svelte-kit",
}

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".cs",
    ".swift", ".kt", ".scala",
    ".html", ".css", ".scss", ".sass", ".less",
    ".yaml", ".yml", ".json", ".toml", ".xml",
    ".ini", ".cfg", ".sh", ".bash", ".zsh",
    ".sql", ".graphql", ".gql", ".tf", ".hcl",
    ".dockerfile", ".makefile",
}

_DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".tex"}

# Files whose content is pure logic/algorithms (not configs or markup)
_IMPL_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".cs",
    ".swift", ".kt", ".scala",
}

_ENCODING = tiktoken.get_encoding("cl100k_base")

_CODE_SPLITTER = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE_CODE,
    chunk_overlap=CHUNK_OVERLAP_CODE,
)
_DOC_SPLITTER = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE_DOC,
    chunk_overlap=CHUNK_OVERLAP_DOC,
)


def _count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using cl100k_base encoding.

    Args:
        text: The input string to tokenize.

    Returns:
        int: Number of tokens in the text.
    """
    return len(_ENCODING.encode(text))


def _classify(path: Path) -> Literal["code", "doc", "skip"]:
    """
    Classify a file as code, doc, or skip based on its extension.

    Args:
        path: The file path to classify.

    Returns:
        Literal["code", "doc", "skip"]: Classification result.
    """
    ext = path.suffix.lower()
    name = path.name.lower()
    if name in {"dockerfile", "makefile", "gemfile", "rakefile", "procfile"}:
        return "code"
    if ext in _CODE_EXTENSIONS:
        return "code"
    if ext in _DOC_EXTENSIONS:
        return "doc"
    return "skip"


def _clone_repo(repo_url: str) -> str:
    """
    Shallow-clone a public GitHub repository into a temporary directory.

    Args:
        repo_url: HTTPS URL of the public GitHub repository.

    Returns:
        str: Path to the cloned repository on disk.

    Raises:
        git.GitCommandError: If the clone fails (e.g., repo not found).
    """
    tmp = tempfile.mkdtemp(prefix="repolens_")
    print(f"  Cloning {repo_url} → {tmp}")
    git.Repo.clone_from(repo_url, tmp, depth=1)
    return tmp


def _walk_files(repo_path: str) -> List[Path]:
    """
    Walk a repository directory and return all non-skipped file paths.

    Args:
        repo_path: Absolute path to the cloned repository root.

    Returns:
        List[Path]: Absolute paths of files to process.
    """
    root = Path(repo_path)
    result: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Skip any file whose ancestry contains a skipped directory name
        parts = {p.name for p in path.parents}
        if parts & _SKIP_DIRS:
            continue
        result.append(path)
    return result


def load_repo_documents(repo_url: str) -> List[Document]:
    """
    Clone a GitHub repository, chunk its files, and return LangChain Documents.

    Each Document carries metadata: file_path (repo-relative), type (code/doc),
    is_code, is_implementation, and chunk_index.

    Args:
        repo_url: HTTPS URL of a public GitHub repository.

    Returns:
        List[Document]: Chunked documents ready for embedding.
    """
    repo_path = _clone_repo(repo_url)
    try:
        return _process_repo(repo_path)
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def _process_repo(repo_path: str) -> List[Document]:
    """
    Walk and chunk all eligible files in a cloned repository.

    Args:
        repo_path: Absolute path to the cloned repository root.

    Returns:
        List[Document]: All document chunks with metadata attached.
    """
    root = Path(repo_path)
    files = _walk_files(repo_path)
    print(f"  Found {len(files)} candidate files")

    all_docs: List[Document] = []
    skipped = 0

    for file_path in files:
        file_type = _classify(file_path)
        if file_type == "skip":
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not content.strip():
            continue

        token_count = _count_tokens(content)
        max_tokens = MAX_TOKENS_CODE if file_type == "code" else MAX_TOKENS_DOC
        if token_count > max_tokens:
            skipped += 1
            continue

        rel_path = str(file_path.relative_to(root))
        is_code = file_type == "code"
        is_impl = file_path.suffix.lower() in _IMPL_EXTENSIONS

        splitter = _CODE_SPLITTER if file_type == "code" else _DOC_SPLITTER
        chunks = splitter.split_text(content)

        for i, chunk in enumerate(chunks):
            all_docs.append(Document(
                page_content=chunk,
                metadata={
                    "file_path": rel_path,
                    "type": file_type,
                    "is_code": is_code,
                    "is_implementation": is_impl,
                    "chunk_index": i,
                },
            ))

    print(f"  Produced {len(all_docs)} chunks ({skipped} files skipped — too large)")
    return all_docs


# ---------------------------------------------------------------------------
# Repo context (file tree + README) — used by /wiki/structure
# ---------------------------------------------------------------------------

_README_MAX_CHARS = 8000


def get_repo_context(repo_url: str) -> Tuple[str, str]:
    """
    Shallow-clone a repository and extract its file tree and README content.

    Reuses _clone_repo and _walk_files so no duplicate clone logic exists.

    Args:
        repo_url: HTTPS URL of a public GitHub repository.

    Returns:
        Tuple[str, str]: (file_tree, readme_content) where file_tree is a
            sorted, newline-separated list of repo-relative file paths and
            readme_content is the raw README text (up to 8 000 characters).

    Raises:
        git.GitCommandError: If the clone fails (e.g., repo not found or private).
    """
    repo_path = _clone_repo(repo_url)
    try:
        root = Path(repo_path)
        # Reuse _walk_files, then filter out extension-skipped files and sort
        all_paths = _walk_files(repo_path)
        file_list = sorted(
            str(p.relative_to(root))
            for p in all_paths
            if _classify(p) != "skip"
        )
        file_tree = "\n".join(file_list)
        readme = _find_readme(root)
        return file_tree, readme
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def _find_readme(root: Path) -> str:
    """
    Find and return the content of the repository's README file.

    Checks common README filenames in order and returns the first match,
    truncated to _README_MAX_CHARS characters.

    Args:
        root: Absolute path to the cloned repository root.

    Returns:
        str: README content (up to 8 000 characters), or a placeholder if
            no README is found.
    """
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        candidate = root / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="ignore")[:_README_MAX_CHARS]
    return "(No README found)"
