#!/usr/bin/env python3
"""
CSNL Paper Scout Embedding Utility

This module wraps the OpenRouter Embeddings API for the CSNL Paper Scout pipeline.
It provides multimodal embedding capabilities (text + images) using the free tier of
nvidia/llama-nemotron-embed-vl-1b-v2 model and supports vector database operations.

Pipeline Integration:
  - Phase 1 (Scan): embed_text() for abstract embedding, search_vectors() for anchor expansion
  - Phase 2 (Score): rerank() for candidate reranking by member relevance
  - Phase 3 (Draft): embed_image() for figure selection, cosine_similarity() for matching

Author: CSNL AI Agent
License: Internal Use
"""

import json
import math
import os
import sys
import time
import argparse
import requests
from typing import List, Dict, Union, Optional, Tuple


# Constants
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"
OPENROUTER_RERANK_ENDPOINT = "https://openrouter.ai/api/v1/rerank"
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
RERANK_MODEL = "nvidia/llama-nemotron-rerank-vl-1b-v2:free"
EMBEDDING_DIM = 2048
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0  # exponential backoff: 1s, 2s, 4s
REQUEST_TIMEOUT = 30


class EmbeddingError(Exception):
    """Custom exception for embedding operations"""
    pass


class VectorDatabaseError(Exception):
    """Custom exception for vector database operations"""
    pass


def _get_headers() -> Dict[str, str]:
    """
    Build request headers for OpenRouter API.
    
    Returns:
        Dict[str, str]: Headers with API key and metadata
        
    Raises:
        EmbeddingError: If OPENROUTER_API_KEY environment variable is not set
    """
    if not OPENROUTER_API_KEY:
        raise EmbeddingError(
            "OPENROUTER_API_KEY environment variable not set. "
            "Please set it to your OpenRouter API key."
        )
    
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://csnl.snu.ac.kr",
        "X-Title": "CSNL Paper Scout"
    }


def _retry_request(
    method: str,
    url: str,
    json_data: Dict,
    max_retries: int = MAX_RETRIES
) -> Dict:
    """
    Make HTTP request with exponential backoff retry logic.
    
    Args:
        method: HTTP method ('POST', 'GET', etc.)
        url: API endpoint URL
        json_data: Request payload
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict: Parsed JSON response
        
    Raises:
        EmbeddingError: If request fails after all retries
    """
    headers = _get_headers()
    
    for attempt in range(max_retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                json=json_data,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise EmbeddingError(f"Request timeout after {max_retries} retries")
            wait_time = RETRY_BACKOFF_BASE ** attempt
            time.sleep(wait_time)
            
        except requests.exceptions.HTTPError as e:
            # Rate limit: 429
            if e.response.status_code == 429:
                if attempt == max_retries - 1:
                    raise EmbeddingError(
                        f"Rate limited after {max_retries} retries. "
                        "Please wait before retrying."
                    )
                wait_time = RETRY_BACKOFF_BASE ** attempt
                time.sleep(wait_time)
            # Other HTTP errors
            else:
                raise EmbeddingError(
                    f"HTTP {e.response.status_code}: {e.response.text}"
                )
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise EmbeddingError(f"Request failed after {max_retries} retries: {str(e)}")
            wait_time = RETRY_BACKOFF_BASE ** attempt
            time.sleep(wait_time)


def embed_text(text: str) -> List[float]:
    """
    Embed a text string to a 2048-dimensional vector.
    
    Used in Phase 1 (Scan) for abstract embedding.
    
    Args:
        text: Text content to embed
        
    Returns:
        List[float]: 2048-dimensional embedding vector
        
    Raises:
        EmbeddingError: If embedding fails
    """
    if not isinstance(text, str):
        raise EmbeddingError(f"text must be a string, got {type(text)}")
    
    if len(text.strip()) == 0:
        raise EmbeddingError("text cannot be empty")
    
    payload = {
        "model": EMBED_MODEL,
        "input": text
    }
    
    response = _retry_request("POST", OPENROUTER_ENDPOINT, payload)
    
    if "data" not in response or len(response["data"]) == 0:
        raise EmbeddingError("No embedding returned from API")
    
    embedding = response["data"][0].get("embedding")
    if not embedding:
        raise EmbeddingError("Invalid embedding response format")
    
    return embedding


def embed_image(image_url: str) -> List[float]:
    """
    Embed an image URL to a 2048-dimensional vector.
    
    Used in Phase 3 (Draft) for figure selection.
    
    Args:
        image_url: URL of the image to embed
        
    Returns:
        List[float]: 2048-dimensional embedding vector
        
    Raises:
        EmbeddingError: If embedding fails
    """
    if not isinstance(image_url, str):
        raise EmbeddingError(f"image_url must be a string, got {type(image_url)}")
    
    if not image_url.strip():
        raise EmbeddingError("image_url cannot be empty")
    
    payload = {
        "model": EMBED_MODEL,
        "input": image_url
    }
    
    response = _retry_request("POST", OPENROUTER_ENDPOINT, payload)
    
    if "data" not in response or len(response["data"]) == 0:
        raise EmbeddingError("No embedding returned from API")
    
    embedding = response["data"][0].get("embedding")
    if not embedding:
        raise EmbeddingError("Invalid embedding response format")
    
    return embedding


def embed_multimodal(text: str, image_url: str) -> List[float]:
    """
    Embed text + image combined to a single 2048-dimensional vector.
    
    Multimodal models fuse both modalities into a shared embedding space.
    
    Args:
        text: Text content to embed
        image_url: URL of the image to embed
        
    Returns:
        List[float]: 2048-dimensional embedding vector
        
    Raises:
        EmbeddingError: If embedding fails
    """
    if not isinstance(text, str):
        raise EmbeddingError(f"text must be a string, got {type(text)}")
    if not isinstance(image_url, str):
        raise EmbeddingError(f"image_url must be a string, got {type(image_url)}")
    
    if len(text.strip()) == 0:
        raise EmbeddingError("text cannot be empty")
    if not image_url.strip():
        raise EmbeddingError("image_url cannot be empty")
    
    # Combine text and image URL in a format the model understands
    combined_input = f"Text: {text}\nImage: {image_url}"
    
    payload = {
        "model": EMBED_MODEL,
        "input": combined_input
    }
    
    response = _retry_request("POST", OPENROUTER_ENDPOINT, payload)
    
    if "data" not in response or len(response["data"]) == 0:
        raise EmbeddingError("No embedding returned from API")
    
    embedding = response["data"][0].get("embedding")
    if not embedding:
        raise EmbeddingError("Invalid embedding response format")
    
    return embedding


def embed_batch(inputs: List[Dict[str, str]]) -> List[List[float]]:
    """
    Batch embed multiple items efficiently.
    
    Args:
        inputs: List of dicts with 'text' and/or 'image_url' keys
                Example: [{"text": "abstract text"}, {"image_url": "https://..."}, 
                         {"text": "...", "image_url": "..."}]
        
    Returns:
        List[List[float]]: List of 2048-dimensional embedding vectors
        
    Raises:
        EmbeddingError: If embedding fails
    """
    if not isinstance(inputs, list):
        raise EmbeddingError(f"inputs must be a list, got {type(inputs)}")
    
    if len(inputs) == 0:
        raise EmbeddingError("inputs cannot be empty")
    
    embeddings = []
    
    for i, item in enumerate(inputs):
        if not isinstance(item, dict):
            raise EmbeddingError(f"Item {i} is not a dict: {type(item)}")
        
        text = item.get("text", "").strip()
        image_url = item.get("image_url", "").strip()
        
        if not text and not image_url:
            raise EmbeddingError(f"Item {i} has neither 'text' nor 'image_url'")
        
        if text and image_url:
            embedding = embed_multimodal(text, image_url)
        elif text:
            embedding = embed_text(text)
        else:
            embedding = embed_image(image_url)
        
        embeddings.append(embedding)
    
    return embeddings


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Used in Phase 3 (Draft) for member-figure matching.
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        float: Cosine similarity score in range [-1, 1]
        
    Raises:
        EmbeddingError: If vectors have different dimensions
    """
    if not isinstance(a, list) or not isinstance(b, list):
        raise EmbeddingError("Both arguments must be lists")
    
    if len(a) != len(b):
        raise EmbeddingError(
            f"Vector dimensions must match: {len(a)} != {len(b)}"
        )
    
    if len(a) == 0:
        raise EmbeddingError("Vectors cannot be empty")
    
    # Compute dot product
    dot_product = sum(x * y for x, y in zip(a, b))
    
    # Compute norms
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    
    # Handle zero vectors
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def search_vectors(
    query_vec: List[float],
    db: List[Dict],
    top_k: int = 5
) -> List[Dict]:
    """
    Search a vector database by cosine similarity.
    
    Used in Phase 1 (Scan) for anchor expansion.
    
    Args:
        query_vec: Query embedding vector
        db: List of dicts with 'embedding' key (and other metadata)
        top_k: Number of top matches to return
        
    Returns:
        List[Dict]: Top-k matches with added 'similarity_score' field, sorted by score (desc)
        
    Raises:
        EmbeddingError: If search fails
    """
    if not isinstance(query_vec, list):
        raise EmbeddingError(f"query_vec must be a list, got {type(query_vec)}")
    
    if not isinstance(db, list):
        raise EmbeddingError(f"db must be a list, got {type(db)}")
    
    if len(db) == 0:
        return []
    
    if top_k <= 0:
        raise EmbeddingError("top_k must be positive")
    
    # Compute similarities
    results = []
    for item in db:
        if "embedding" not in item:
            continue
        
        similarity = cosine_similarity(query_vec, item["embedding"])
        result = dict(item)  # Copy item
        result["similarity_score"] = similarity
        results.append(result)
    
    # Sort by similarity (descending) and return top-k
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:top_k]


def rerank(
    query: str,
    documents: List[str],
    top_k: int = 5
) -> List[Dict]:
    """
    Rerank documents using the Nemotron rerank model.
    
    Used in Phase 2 (Score) for candidate reranking by member relevance.
    
    Args:
        query: Search query or relevance criteria
        documents: List of document texts to rerank
        top_k: Number of top-ranked documents to return
        
    Returns:
        List[Dict]: Reranked documents with 'text', 'rank', and 'score' fields
        
    Raises:
        EmbeddingError: If reranking fails
    """
    if not isinstance(query, str) or not query.strip():
        raise EmbeddingError("query must be a non-empty string")
    
    if not isinstance(documents, list) or len(documents) == 0:
        raise EmbeddingError("documents must be a non-empty list")
    
    if top_k <= 0:
        raise EmbeddingError("top_k must be positive")
    
    # Validate all documents are strings
    for i, doc in enumerate(documents):
        if not isinstance(doc, str):
            raise EmbeddingError(f"Document {i} is not a string: {type(doc)}")
    
    payload = {
        "model": RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_k": min(top_k, len(documents))
    }
    
    response = _retry_request("POST", OPENROUTER_ENDPOINT, payload)
    
    if "results" not in response:
        raise EmbeddingError("Invalid rerank response format")
    
    results = []
    for result in response["results"]:
        results.append({
            "text": documents[result["index"]],
            "rank": result.get("index"),
            "score": result.get("score", 0.0)
        })
    
    return results


def load_vector_db(path: str) -> List[Dict]:
    """
    Load a vector database from a JSON file.
    
    Args:
        path: File path to the JSON vector database
        
    Returns:
        List[Dict]: Vector database as list of paper dicts
        
    Raises:
        VectorDatabaseError: If file does not exist or is invalid JSON
    """
    if not isinstance(path, str):
        raise VectorDatabaseError(f"path must be a string, got {type(path)}")
    
    if not os.path.exists(path):
        raise VectorDatabaseError(f"Vector database file not found: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            db = json.load(f)
        
        if not isinstance(db, list):
            raise VectorDatabaseError(
                f"Vector database must be a list, got {type(db)}"
            )
        
        return db
    
    except json.JSONDecodeError as e:
        raise VectorDatabaseError(f"Invalid JSON in vector database: {str(e)}")
    except IOError as e:
        raise VectorDatabaseError(f"Error reading vector database: {str(e)}")


def save_vector_db(db: List[Dict], path: str) -> None:
    """
    Save a vector database to a JSON file.
    
    Args:
        db: Vector database as list of paper dicts
        path: File path to save the JSON vector database
        
    Raises:
        VectorDatabaseError: If save fails
    """
    if not isinstance(db, list):
        raise VectorDatabaseError(f"db must be a list, got {type(db)}")
    
    if not isinstance(path, str):
        raise VectorDatabaseError(f"path must be a string, got {type(path)}")
    
    try:
        # Create parent directory if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    
    except IOError as e:
        raise VectorDatabaseError(f"Error writing vector database: {str(e)}")


def upsert_paper(db: List[Dict], paper: Dict) -> List[Dict]:
    """
    Add or update a paper in the vector database.
    
    Paper dict should contain:
        - doi: Digital Object Identifier (unique key)
        - title: Paper title
        - authors: List of author names
        - abstract: Paper abstract
        - year: Publication year
        - venue: Journal/conference name
        - embedding: 2048-dim embedding of abstract
        - figure_embeddings (optional): List of figure embeddings
        - equation_embeddings (optional): List of equation embeddings
    
    Args:
        db: Current vector database
        paper: Paper dict to add/update
        
    Returns:
        List[Dict]: Updated database
        
    Raises:
        VectorDatabaseError: If paper dict is invalid
    """
    if not isinstance(db, list):
        raise VectorDatabaseError(f"db must be a list, got {type(db)}")
    
    if not isinstance(paper, dict):
        raise VectorDatabaseError(f"paper must be a dict, got {type(paper)}")
    
    # Validate required fields
    required_fields = ["doi", "title", "authors", "abstract", "year", "venue", "embedding"]
    for field in required_fields:
        if field not in paper:
            raise VectorDatabaseError(f"Paper missing required field: {field}")
    
    # Validate embedding dimension
    if not isinstance(paper["embedding"], list):
        raise VectorDatabaseError(
            f"Paper embedding must be a list, got {type(paper['embedding'])}"
        )
    if len(paper["embedding"]) != EMBEDDING_DIM:
        raise VectorDatabaseError(
            f"Paper embedding must be {EMBEDDING_DIM}-dimensional, "
            f"got {len(paper['embedding'])}"
        )
    
    # Find and remove existing paper by DOI
    db = [p for p in db if p.get("doi") != paper["doi"]]
    
    # Append new/updated paper
    db.append(paper)
    
    return db


# ============================================================================
# CLI Interface
# ============================================================================

def cli_embed_text(text: str) -> None:
    """CLI: embed-text command"""
    try:
        embedding = embed_text(text)
        print(json.dumps(embedding, indent=2))
    except EmbeddingError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_embed_image(image_url: str) -> None:
    """CLI: embed-image command"""
    try:
        embedding = embed_image(image_url)
        print(json.dumps(embedding, indent=2))
    except EmbeddingError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_search(
    query: str,
    db_path: str,
    top_k: int = 5
) -> None:
    """CLI: search command"""
    try:
        # Load database
        db = load_vector_db(db_path)
        
        # Embed query
        query_vec = embed_text(query)
        
        # Search
        results = search_vectors(query_vec, db, top_k)
        
        # Print results
        print(json.dumps(results, indent=2))
    except (EmbeddingError, VectorDatabaseError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_rerank(query: str, documents: List[str]) -> None:
    """CLI: rerank command"""
    try:
        results = rerank(query, documents)
        print(json.dumps(results, indent=2))
    except EmbeddingError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_build_anchor_db(zotero_export: str, output: str) -> None:
    """CLI: build-anchor-db command"""
    try:
        # Load Zotero export
        with open(zotero_export, "r", encoding="utf-8") as f:
            papers = json.load(f)
        
        if not isinstance(papers, list):
            papers = [papers]
        
        # Build vector database
        vector_db = []
        for i, paper in enumerate(papers):
            print(f"Embedding paper {i+1}/{len(papers)}: {paper.get('title', 'Unknown')}")
            
            # Extract fields
            doi = paper.get("doi", paper.get("DOI", f"unknown-{i}"))
            title = paper.get("title", "")
            authors = paper.get("author", [])
            if isinstance(authors, str):
                authors = [authors]
            abstract = paper.get("abstract", "")
            year = paper.get("year", 0)
            venue = paper.get("publicationTitle", paper.get("venue", ""))
            
            # Embed abstract
            if abstract:
                embedding = embed_text(abstract)
            else:
                embedding = [0.0] * EMBEDDING_DIM
            
            # Create paper record
            paper_record = {
                "doi": doi,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "year": year,
                "venue": venue,
                "embedding": embedding
            }
            
            vector_db.append(paper_record)
        
        # Save database
        save_vector_db(vector_db, output)
        print(f"Saved {len(vector_db)} papers to {output}")
    
    except (IOError, json.JSONDecodeError, EmbeddingError, VectorDatabaseError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="CSNL Paper Scout Embedding Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python paper-scout-embed.py embed-text "Deep learning abstracts"
  python paper-scout-embed.py embed-image "https://example.com/fig.png"
  python paper-scout-embed.py search "attention mechanisms" --db db.json --top_k 5
  python paper-scout-embed.py rerank "relevant to neuroscience" --docs "doc1" "doc2"
  python paper-scout-embed.py build-anchor-db --zotero-export papers.json --output db.json
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # embed-text
    embed_text_parser = subparsers.add_parser("embed-text", help="Embed text")
    embed_text_parser.add_argument("text", help="Text to embed")
    
    # embed-image
    embed_image_parser = subparsers.add_parser("embed-image", help="Embed image URL")
    embed_image_parser.add_argument("image_url", help="Image URL to embed")
    
    # search
    search_parser = subparsers.add_parser("search", help="Search vector database")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--db", required=True, help="Path to vector database")
    search_parser.add_argument("--top_k", type=int, default=5, help="Number of results")
    
    # rerank
    rerank_parser = subparsers.add_parser("rerank", help="Rerank documents")
    rerank_parser.add_argument("query", help="Reranking query")
    rerank_parser.add_argument(
        "--docs",
        nargs="+",
        required=True,
        help="Documents to rerank"
    )
    
    # build-anchor-db
    build_parser = subparsers.add_parser(
        "build-anchor-db",
        help="Build vector database from Zotero export"
    )
    build_parser.add_argument(
        "--zotero-export",
        required=True,
        help="Path to Zotero JSON export"
    )
    build_parser.add_argument(
        "--output",
        required=True,
        help="Path to save vector database"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Dispatch commands
    if args.command == "embed-text":
        cli_embed_text(args.text)
    elif args.command == "embed-image":
        cli_embed_image(args.image_url)
    elif args.command == "search":
        cli_search(args.query, args.db, args.top_k)
    elif args.command == "rerank":
        cli_rerank(args.query, args.docs)
    elif args.command == "build-anchor-db":
        cli_build_anchor_db(args.zotero_export, args.output)


if __name__ == "__main__":
    main()
