#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import httpx
from rapidfuzz import fuzz


DEFAULT_HF_DATASET = "explodinggradients/amnesty_qa"
DEFAULT_HF_CONFIG = "english_v3"
DEFAULT_HF_SPLIT = "eval"
DEFAULT_CONTEXT_MATCH_THRESHOLD = 0.85
DEFAULT_ANSWER_MATCH_THRESHOLD = 0.70


@dataclass
class BenchmarkSample:
    sample_id: str
    question: str
    ground_truth: str
    reference_contexts: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalRunConfig:
    base_url: str
    username: str
    password: str
    dataset_source: str
    dataset_path: str | None
    hf_dataset: str
    hf_config: str | None
    hf_split: str
    hf_trust_remote_code: bool
    limit: int
    top_k: int
    batch_size: int
    reset_first: bool
    force_reingest: bool
    embedding_profile: str | None
    embedding_provider: str | None
    embedding_model: str | None
    generation_provider: str | None
    generation_model: str | None
    eval_llm_model: str | None
    eval_llm_base_url: str | None
    eval_llm_api_key: str | None
    eval_embedding_model: str | None
    eval_embedding_base_url: str | None
    eval_embedding_api_key: str | None
    output_dir: str


class BackendRagClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_seconds)
        self._headers: dict[str, str] = {}

    async def __aenter__(self) -> "BackendRagClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.aclose()

    async def login(self) -> None:
        response = await self._client.post(
            "/auth/token",
            json={"username": self._username, "password": self._password},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError(f"Login succeeded but no access token was returned: {payload}")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def reset(self) -> dict[str, Any]:
        response = await self._client.delete("/admin/reset", headers=self._headers)
        response.raise_for_status()
        return response.json()

    async def ingest_text_items(
        self,
        *,
        items: list[dict[str, Any]],
        embedding_profile: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
        force_reingest: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "items": items,
            "force_reingest": force_reingest,
        }
        if embedding_profile:
            payload["embedding_profile"] = embedding_profile
        if embedding_provider:
            payload["embedding_provider"] = embedding_provider
        if embedding_model:
            payload["embedding_model"] = embedding_model

        response = await self._client.post("/ingest/text", headers=self._headers, json=payload)
        response.raise_for_status()
        return response.json()

    async def chat(
        self,
        *,
        message: str,
        top_k: int,
        generation_provider: str | None,
        generation_model: str | None,
        embedding_profile: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "debug": True,
            "top_k": top_k,
        }
        if generation_provider:
            payload["provider"] = generation_provider
        if generation_model:
            payload["model"] = generation_model
        if embedding_profile:
            payload["embedding_profile"] = embedding_profile
        if embedding_provider:
            payload["embedding_provider"] = embedding_provider
        if embedding_model:
            payload["embedding_model"] = embedding_model

        response = await self._client.post("/chat", headers=self._headers, json=payload)
        response.raise_for_status()
        return response.json()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the backend RAG chatbot with RAGAS against a public or local dataset."
    )
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL"), help="Backend base URL.")
    parser.add_argument("--username", default=os.environ.get("RAG_EVAL_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("RAG_EVAL_PASSWORD"))
    parser.add_argument("--dataset-source", choices=["huggingface", "jsonl"], default="huggingface")
    parser.add_argument("--dataset-path", help="Path to a local JSONL benchmark.")
    parser.add_argument("--hf-dataset", default=DEFAULT_HF_DATASET)
    parser.add_argument("--hf-config", default=DEFAULT_HF_CONFIG)
    parser.add_argument("--hf-split", default=DEFAULT_HF_SPLIT)
    parser.add_argument("--hf-trust-remote-code", action="store_true")
    parser.add_argument("--limit", type=int, default=10, help="Max questions to evaluate.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=20, help="Ingest batch size.")
    parser.add_argument("--reset-first", action="store_true", help="Call /admin/reset before ingest.")
    parser.add_argument("--force-reingest", action="store_true", help="Pass force_reingest=true.")
    parser.add_argument("--embedding-profile")
    parser.add_argument("--embedding-provider")
    parser.add_argument("--embedding-model")
    parser.add_argument("--generation-provider")
    parser.add_argument("--generation-model")
    parser.add_argument("--eval-llm-model", default=os.environ.get("RAGAS_EVAL_LLM_MODEL"))
    parser.add_argument(
        "--eval-llm-base-url",
        default=os.environ.get("RAGAS_EVAL_LLM_BASE_URL"),
        help="OpenAI-compatible base URL for the judge LLM.",
    )
    parser.add_argument(
        "--eval-llm-api-key",
        default=os.environ.get("RAGAS_EVAL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--eval-embedding-model",
        default=os.environ.get("RAGAS_EVAL_EMBED_MODEL"),
        help="OpenAI-compatible embedding model for semantic metrics.",
    )
    parser.add_argument(
        "--eval-embedding-base-url",
        default=os.environ.get("RAGAS_EVAL_EMBED_BASE_URL"),
        help="OpenAI-compatible base URL for the evaluator embedding model.",
    )
    parser.add_argument(
        "--eval-embedding-api-key",
        default=os.environ.get("RAGAS_EVAL_EMBED_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for raw outputs. Defaults to eval/output/<timestamp>.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_config(args: argparse.Namespace) -> EvalRunConfig:
    repo_root = Path(__file__).resolve().parents[1]
    backend_env = load_env_file(repo_root / "backend" / ".env")

    base_url = args.base_url
    if not base_url:
        app_port = backend_env.get("APP_PORT", "9010")
        base_url = f"http://localhost:{app_port}"
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"

    username = args.username or backend_env.get("AUTH_BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = args.password or backend_env.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD")

    output_dir = args.output_dir
    if not output_dir:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = str(Path(__file__).resolve().parent / "output" / timestamp)

    if not password:
        raise RuntimeError(
            "Missing password. Set RAG_EVAL_PASSWORD or backend/.env AUTH_BOOTSTRAP_ADMIN_PASSWORD."
        )

    if args.dataset_source == "jsonl" and not args.dataset_path:
        raise RuntimeError("--dataset-path is required when --dataset-source jsonl is used.")

    return EvalRunConfig(
        base_url=base_url,
        username=username,
        password=password,
        dataset_source=args.dataset_source,
        dataset_path=args.dataset_path,
        hf_dataset=args.hf_dataset,
        hf_config=args.hf_config,
        hf_split=args.hf_split,
        hf_trust_remote_code=args.hf_trust_remote_code,
        limit=args.limit,
        top_k=args.top_k,
        batch_size=args.batch_size,
        reset_first=args.reset_first,
        force_reingest=args.force_reingest,
        embedding_profile=args.embedding_profile,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
        generation_provider=args.generation_provider,
        generation_model=args.generation_model,
        eval_llm_model=args.eval_llm_model,
        eval_llm_base_url=args.eval_llm_base_url,
        eval_llm_api_key=args.eval_llm_api_key,
        eval_embedding_model=args.eval_embedding_model,
        eval_embedding_base_url=args.eval_embedding_base_url,
        eval_embedding_api_key=args.eval_embedding_api_key,
        output_dir=output_dir,
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def coerce_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = first_present(item, ["content", "text", "page_content", "body", "snippet"])
                if candidate:
                    flattened.append(candidate)
            else:
                candidate = normalize_text(item)
                if candidate:
                    flattened.append(candidate)
        return flattened
    return []


def first_present(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        candidate = normalize_text(record.get(key))
        if candidate:
            return candidate
    return ""


def extract_reference_contexts(record: dict[str, Any]) -> list[str]:
    for key in [
        "reference_contexts",
        "reference_context",
        "retrieved_contexts",
        "ground_truth_contexts",
        "contexts",
        "context",
        "documents",
    ]:
        contexts = coerce_text_list(record.get(key))
        if contexts:
            return contexts
    return []


def sample_from_record(record: dict[str, Any], index: int) -> BenchmarkSample:
    question = first_present(record, ["question", "user_input", "query"])
    ground_truth = first_present(
        record,
        [
            "ground_truth",
            "reference",
            "answer",
            "reference_answer",
            "ideal_answer",
        ],
    )
    reference_contexts = extract_reference_contexts(record)

    if not question:
        raise ValueError(f"Record {index} is missing question-like fields.")
    if not ground_truth:
        raise ValueError(f"Record {index} is missing answer/reference-like fields.")
    if not reference_contexts:
        raise ValueError(f"Record {index} is missing context/documents fields.")

    sample_id = normalize_text(record.get("id")) or f"sample-{index:04d}"
    return BenchmarkSample(
        sample_id=sample_id,
        question=question,
        ground_truth=ground_truth,
        reference_contexts=reference_contexts,
        metadata={k: v for k, v in record.items() if k not in {"question", "user_input", "query"}},
    )


def load_jsonl_samples(path: Path, limit: int) -> list[BenchmarkSample]:
    samples: list[BenchmarkSample] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            record = json.loads(raw)
            samples.append(sample_from_record(record, index))
            if len(samples) >= limit:
                break
    return samples


def load_huggingface_samples(
    *,
    dataset_name: str,
    config_name: str | None,
    split_name: str,
    trust_remote_code: bool,
    limit: int,
) -> list[BenchmarkSample]:
    from datasets import load_dataset

    try:
        dataset = load_dataset(
            dataset_name,
            config_name,
            split=split_name,
            trust_remote_code=trust_remote_code,
        )
    except RuntimeError as exc:
        if "Dataset scripts are no longer supported" in str(exc):
            raise RuntimeError(
                "The selected Hugging Face dataset relies on a legacy dataset script, "
                "which the installed `datasets` package no longer supports. "
                "Use a parquet/native dataset such as "
                "`explodinggradients/amnesty_qa` or switch to `--dataset-source jsonl`."
            ) from exc
        raise

    samples: list[BenchmarkSample] = []
    for index, row in enumerate(dataset, start=1):
        samples.append(sample_from_record(dict(row), index))
        if len(samples) >= limit:
            break
    return samples


def load_samples(config: EvalRunConfig) -> list[BenchmarkSample]:
    if config.dataset_source == "jsonl":
        return load_jsonl_samples(Path(config.dataset_path), config.limit)
    return load_huggingface_samples(
        dataset_name=config.hf_dataset,
        config_name=config.hf_config,
        split_name=config.hf_split,
        trust_remote_code=config.hf_trust_remote_code,
        limit=config.limit,
    )


def build_ingest_items(samples: list[BenchmarkSample]) -> list[dict[str, Any]]:
    items_by_hash: dict[str, dict[str, Any]] = {}
    for sample in samples:
        for context_index, context_text in enumerate(sample.reference_contexts, start=1):
            content = normalize_text(context_text)
            if not content:
                continue
            content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()
            items_by_hash.setdefault(
                content_hash,
                {
                    "title": f"{sample.sample_id}-ctx-{context_index}",
                    "content": content,
                    "source_type": "text",
                    "metadata": {
                        "source": "ragas_eval",
                        "sample_id": sample.sample_id,
                    },
                },
            )
    return list(items_by_hash.values())


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def extract_retrieved_contexts(chat_payload: dict[str, Any]) -> list[str]:
    chunks = chat_payload.get("retrieved_chunks", [])
    if not isinstance(chunks, list):
        return []

    contexts: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        content = normalize_text(chunk.get("content"))
        if content:
            contexts.append(content)
    return contexts


def build_ragas_metrics(
    *,
    include_llm_metrics: bool,
    include_embedding_metrics: bool,
) -> list[Any]:
    from ragas.metrics import (
        Faithfulness,
        FactualCorrectness,
        LLMContextRecall,
        NonLLMContextPrecisionWithReference,
        ResponseRelevancy,
        SemanticSimilarity,
    )

    metrics: list[Any] = [NonLLMContextPrecisionWithReference()]
    if include_llm_metrics:
        metrics.extend(
            [
                Faithfulness(),
                ResponseRelevancy(),
                LLMContextRecall(),
                FactualCorrectness(),
            ]
        )
    if include_embedding_metrics:
        metrics.append(SemanticSimilarity())
    return metrics


def build_ragas_models(config: EvalRunConfig) -> tuple[Any | None, Any | None]:
    llm = None
    embeddings = None

    if config.eval_llm_model:
        from langchain_openai import ChatOpenAI

        try:
            from ragas.llms import LangchainLLMWrapper
        except ImportError:
            from ragas.llms.base import LangchainLLMWrapper

        llm_client = ChatOpenAI(
            model=config.eval_llm_model,
            api_key=config.eval_llm_api_key or "dummy",
            base_url=config.eval_llm_base_url,
            temperature=0,
        )
        llm = LangchainLLMWrapper(llm_client)

    if config.eval_embedding_model:
        from langchain_openai import OpenAIEmbeddings

        try:
            from ragas.embeddings import LangchainEmbeddingsWrapper
        except ImportError:
            from ragas.embeddings.base import LangchainEmbeddingsWrapper

        embedding_client = OpenAIEmbeddings(
            model=config.eval_embedding_model,
            api_key=config.eval_embedding_api_key or "dummy",
            base_url=config.eval_embedding_base_url,
        )
        embeddings = LangchainEmbeddingsWrapper(embedding_client)

    return llm, embeddings


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure_output_dir(path: str) -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def ingest_benchmark_contexts(
    client: BackendRagClient,
    config: EvalRunConfig,
    samples: list[BenchmarkSample],
) -> dict[str, int]:
    ingest_items = build_ingest_items(samples)
    totals = {
        "unique_contexts": len(ingest_items),
        "documents_inserted": 0,
        "chunks_inserted": 0,
    }

    for batch_index, batch in enumerate(chunked(ingest_items, config.batch_size), start=1):
        ingest_payload = await client.ingest_text_items(
            items=batch,
            embedding_profile=config.embedding_profile,
            embedding_provider=config.embedding_provider,
            embedding_model=config.embedding_model,
            force_reingest=config.force_reingest,
        )
        totals["documents_inserted"] += int(ingest_payload.get("documents_inserted", 0) or 0)
        totals["chunks_inserted"] += int(ingest_payload.get("chunks_inserted", 0) or 0)
        print(
            f"Ingested batch {batch_index}: "
            f"{ingest_payload.get('documents_inserted', 0)} docs, "
            f"{ingest_payload.get('chunks_inserted', 0)} chunks"
        )

    return totals


async def query_backend_for_sample(
    client: BackendRagClient,
    config: EvalRunConfig,
    sample: BenchmarkSample,
) -> dict[str, Any]:
    chat_payload = await client.chat(
        message=sample.question,
        top_k=config.top_k,
        generation_provider=config.generation_provider,
        generation_model=config.generation_model,
        embedding_profile=config.embedding_profile,
        embedding_provider=config.embedding_provider,
        embedding_model=config.embedding_model,
    )
    result_row = {
        "sample_id": sample.sample_id,
        "question": sample.question,
        "ground_truth": sample.ground_truth,
        "reference_contexts": sample.reference_contexts,
        "response": normalize_text(chat_payload.get("answer")),
        "retrieved_contexts": extract_retrieved_contexts(chat_payload),
        "citations": chat_payload.get("citations", []),
        "used_fallback": bool(chat_payload.get("used_fallback", False)),
        "provider": chat_payload.get("provider"),
        "model": chat_payload.get("model"),
        "metadata": sample.metadata,
    }
    print(
        f"Evaluated {sample.sample_id}: "
        f"fallback={result_row['used_fallback']} "
        f"retrieved_contexts={len(result_row['retrieved_contexts'])}"
    )
    return result_row


async def run_backend_flow(
    config: EvalRunConfig,
    samples: list[BenchmarkSample],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    results: list[dict[str, Any]] = []

    async with BackendRagClient(
        base_url=config.base_url,
        username=config.username,
        password=config.password,
    ) as client:
        await client.login()

        if config.reset_first:
            reset_payload = await client.reset()
            print(f"Reset complete: {json.dumps(reset_payload)}")

        ingest_stats = await ingest_benchmark_contexts(client, config, samples)

        for sample in samples:
            results.append(await query_backend_for_sample(client, config, sample))

    return results, ingest_stats


def evaluate_with_ragas(
    config: EvalRunConfig,
    rows: list[dict[str, Any]],
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    from ragas import EvaluationDataset, SingleTurnSample, evaluate

    llm, embeddings = build_ragas_models(config)
    metrics = build_ragas_metrics(
        include_llm_metrics=llm is not None,
        include_embedding_metrics=embeddings is not None,
    )

    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input=row["question"],
                response=row["response"],
                reference=row["ground_truth"],
                retrieved_contexts=row["retrieved_contexts"],
                reference_contexts=row["reference_contexts"],
            )
            for row in rows
        ]
    )

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=True,
    )

    frame = result.to_pandas()
    ragas_means: dict[str, float] = {}
    per_sample_rows: list[dict[str, Any]] = []
    for column in frame.columns:
        if column == "user_input":
            continue
        values = [value for value in frame[column].tolist() if isinstance(value, (int, float))]
        if values:
            ragas_means[column] = round(sum(values) / len(values), 6)

    for row, (_, score_row) in zip(rows, frame.iterrows(), strict=True):
        per_sample = dict(row)
        for column in frame.columns:
            per_sample[column] = score_row[column]
        per_sample_rows.append(per_sample)

    return ragas_means, per_sample_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
            writer.writerow(serialized)


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 6)


def to_score(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return round(fuzz.token_set_ratio(left, right) / 100.0, 6)


def best_context_match(reference_contexts: list[str], retrieved_contexts: list[str]) -> float:
    best = 0.0
    for reference in reference_contexts:
        for retrieved in retrieved_contexts:
            best = max(best, text_similarity(reference, retrieved))
    return round(best, 6)


def count_scores_at_or_above(values: list[float], threshold: float) -> int:
    return sum(1 for value in values if value >= threshold)


def build_diagnostic_row(row: dict[str, Any], quality_score: float | None) -> dict[str, Any]:
    return {
        "sample_id": row["sample_id"],
        "question": row["question"],
        "quality_score": quality_score,
        "used_fallback": row["used_fallback"],
        "retrieved_contexts": len(row.get("retrieved_contexts", [])),
        "response_preview": normalize_text(row.get("response"))[:200],
        "ground_truth_preview": normalize_text(row.get("ground_truth"))[:200],
    }


def build_summary(
    config: EvalRunConfig,
    rows: list[dict[str, Any]],
    ragas_means: dict[str, float],
    ingest_stats: dict[str, int],
) -> dict[str, Any]:
    answer_similarity_scores = [
        text_similarity(row["response"], row["ground_truth"])
        for row in rows
    ]
    context_match_scores = [
        best_context_match(row["reference_contexts"], row["retrieved_contexts"])
        for row in rows
    ]
    retrieved_counts = [len(row["retrieved_contexts"]) for row in rows]
    citation_counts = [len(row.get("citations", [])) for row in rows]
    response_lengths = [len(normalize_text(row["response"])) for row in rows]
    answered_count = sum(1 for row in rows if normalize_text(row["response"]))
    fallback_count = sum(1 for row in rows if row["used_fallback"])
    retrieved_count = sum(1 for row in rows if row["retrieved_contexts"])

    for row, answer_similarity, context_match in zip(
        rows, answer_similarity_scores, context_match_scores, strict=True
    ):
        row["answer_similarity"] = answer_similarity
        row["retrieval_context_match"] = context_match

    available_quality_metrics = [
        metric_name
        for metric_name in [
            "factual_correctness",
            "faithfulness",
            "semantic_similarity",
            "response_relevancy",
        ]
        if metric_name in ragas_means
    ]
    quality_values: list[float] = []
    for row in rows:
        numeric_components = [
            score
            for score in (to_score(row.get(metric_name)) for metric_name in available_quality_metrics)
            if score is not None
        ]
        if numeric_components:
            row["quality_score"] = round(sum(numeric_components) / len(numeric_components), 6)
            quality_values.append(row["quality_score"])
        else:
            row["quality_score"] = None

    weakest_samples = [
        build_diagnostic_row(row, row["quality_score"])
        for row in sorted(
            rows,
            key=lambda item: (
                1 if item.get("quality_score") is None else 0,
                item.get("quality_score") if item.get("quality_score") is not None else 999.0,
                item["answer_similarity"],
            ),
        )[:5]
    ]

    return {
        "run": {
            "num_samples": len(rows),
            "dataset_source": config.dataset_source,
            "judge_llm_model": config.eval_llm_model,
            "judge_embedding_model": config.eval_embedding_model,
        },
        "operational": {
            "answered_rate": round(answered_count / len(rows), 6),
            "fallback_rate": round(fallback_count / len(rows), 6),
            "retrieval_hit_rate": round(retrieved_count / len(rows), 6),
            "avg_retrieved_contexts": safe_mean([float(value) for value in retrieved_counts]),
            "avg_citations": safe_mean([float(value) for value in citation_counts]),
            "avg_response_chars": safe_mean([float(value) for value in response_lengths]),
            "unique_contexts_ingested": ingest_stats["unique_contexts"],
            "documents_inserted": ingest_stats["documents_inserted"],
            "chunks_inserted": ingest_stats["chunks_inserted"],
        },
        "retrieval": {
            "ragas_context_precision": ragas_means.get("context_precision"),
            "ragas_context_recall": ragas_means.get("context_recall"),
            "avg_context_match": safe_mean(context_match_scores),
            "context_match_rate_at_0_85": round(
                count_scores_at_or_above(context_match_scores, DEFAULT_CONTEXT_MATCH_THRESHOLD) / len(rows),
                6,
            ),
        },
        "generation": {
            "ragas_faithfulness": ragas_means.get("faithfulness"),
            "ragas_factual_correctness": ragas_means.get("factual_correctness"),
            "ragas_response_relevancy": ragas_means.get("response_relevancy"),
            "ragas_semantic_similarity": ragas_means.get("semantic_similarity"),
            "avg_answer_similarity": safe_mean(answer_similarity_scores),
            "answer_match_rate_at_0_70": round(
                count_scores_at_or_above(answer_similarity_scores, DEFAULT_ANSWER_MATCH_THRESHOLD) / len(rows),
                6,
            ),
            "avg_quality_score": safe_mean(quality_values),
            "quality_pass_rate_at_0_70": (
                round(count_scores_at_or_above(quality_values, 0.70) / len(quality_values), 6)
                if quality_values
                else None
            ),
        },
        "raw_ragas_metrics": ragas_means,
        "weakest_samples": weakest_samples,
    }


def build_config_snapshot(config: EvalRunConfig) -> dict[str, Any]:
    return {
        "base_url": config.base_url,
        "username": config.username,
        "dataset_source": config.dataset_source,
        "dataset_path": config.dataset_path,
        "hf_dataset": config.hf_dataset,
        "hf_config": config.hf_config,
        "hf_split": config.hf_split,
        "limit": config.limit,
        "top_k": config.top_k,
        "batch_size": config.batch_size,
        "reset_first": config.reset_first,
        "force_reingest": config.force_reingest,
        "embedding_profile": config.embedding_profile,
        "embedding_provider": config.embedding_provider,
        "embedding_model": config.embedding_model,
        "generation_provider": config.generation_provider,
        "generation_model": config.generation_model,
        "eval_llm_model": config.eval_llm_model,
        "eval_llm_base_url": config.eval_llm_base_url,
        "eval_embedding_model": config.eval_embedding_model,
        "eval_embedding_base_url": config.eval_embedding_base_url,
    }


async def async_main() -> None:
    config = build_config(parse_args())
    output_dir = ensure_output_dir(config.output_dir)

    samples = load_samples(config)

    if not samples:
        raise RuntimeError("No benchmark samples were loaded.")

    backend_rows, ingest_stats = await run_backend_flow(config, samples)
    ragas_means, per_sample_rows = evaluate_with_ragas(config, backend_rows)
    summary = build_summary(config, per_sample_rows, ragas_means, ingest_stats)

    write_json(output_dir / "config.json", build_config_snapshot(config))
    write_json(output_dir / "summary.json", summary)
    write_jsonl(output_dir / "backend_results.jsonl", backend_rows)
    write_jsonl(output_dir / "ragas_scored_results.jsonl", per_sample_rows)
    write_csv(output_dir / "ragas_scored_results.csv", per_sample_rows)

    print("\nEvaluation summary")
    print(json.dumps(summary, indent=2))
    print(f"\nArtifacts written to: {output_dir}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
