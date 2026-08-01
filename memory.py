from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from openai import OpenAI

from config import Settings
from models import ClassificationResult, EmailMessage


logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.memory_dir.mkdir(parents=True, exist_ok=True)
        self.local_path = self.settings.memory_dir / "local_memory.jsonl"
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._chroma = None
        if settings.memory_backend == "chroma":
            try:
                import chromadb

                chroma_client = chromadb.PersistentClient(path=str(settings.memory_dir / "chroma"))
                self._chroma = chroma_client.get_or_create_collection("email_memory")
            except Exception as exc:
                logger.warning("Chroma unavailable, falling back to local memory: %s", exc)

    def add_interaction(
        self,
        message: EmailMessage,
        classification: ClassificationResult,
        action_summary: str,
    ) -> None:
        text = self._memory_text(message, classification, action_summary)
        record = {
            "uid": message.uid,
            "sender": message.sender,
            "subject": message.subject,
            "category": classification.category.value,
            "priority_score": classification.priority_score,
            "text": text,
            "embedding": self._embed(text),
        }

        if self._chroma is not None and record["embedding"]:
            self._chroma.add(
                ids=[message.uid],
                documents=[text],
                metadatas=[{"sender": message.sender, "category": classification.category.value}],
                embeddings=[record["embedding"]],
            )
            return

        with self.local_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

    def search(self, query: str, limit: int = 5) -> list[str]:
        query_embedding = self._embed(query)
        if self._chroma is not None and query_embedding:
            result = self._chroma.query(query_embeddings=[query_embedding], n_results=limit)
            return list(result.get("documents", [[]])[0])

        records = self._read_local()
        if not records:
            return []
        if not query_embedding:
            return [record["text"] for record in records[-limit:]]

        scored = []
        for record in records:
            embedding = record.get("embedding") or []
            scored.append((self._cosine(query_embedding, embedding), record["text"]))
        scored.sort(reverse=True, key=lambda item: item[0])
        return [text for _, text in scored[:limit]]

    def _embed(self, text: str) -> list[float]:
        if not self.client:
            return []
        try:
            response = self.client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return []

    def _read_local(self) -> list[dict]:
        if not self.local_path.exists():
            return []
        records = []
        with self.local_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    records.append(json.loads(line))
        return records

    @staticmethod
    def _memory_text(message: EmailMessage, classification: ClassificationResult, action_summary: str) -> str:
        return (
            f"Sender: {message.sender}. Subject: {message.subject}. "
            f"Category: {classification.category.value}. Intent: {classification.intent}. "
            f"Action: {action_summary}. Preview: {message.preview}"
        )

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
