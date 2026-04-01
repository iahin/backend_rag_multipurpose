# RAGAS Evaluation

Use a small public benchmark subset and evaluate your RAG in 4 layers:
retrieval
answer quality
grounding / hallucination
latency and failure behavior

support / help center / policy Q&A: Doc2Dial.

long PDFs or papers: QASPER.

combine evidence from multiple docs: Use MultiHop-RAG.


80 percent answerable
20 percent intentionally hard or likely-missed questions

each test case, keep:
question
ground_truth_answer if available
gold_context or supporting passage if available
document_id
your_retrieved_chunks
your_model_answer
latency_ms

For each question:

ingest the benchmark documents into your pipeline
retrieve top-k chunks
generate the answer
log retrieved chunks, answer, and timing

Keep your production-like settings:

same chunking
same embeddings
same reranker if any
same prompt
same top-k
Otherwise the result is not very meaningful.

Metrics to use

A. Recall@k
Did the correct supporting chunk appear in top-k retrieved results?

Example:

if gold evidence is in top 5, count as hit for Recall@5

B. MRR
Measures how early the first relevant chunk appears.

C. nDCG
Useful if there are multiple relevant chunks and ranking quality matters.

$ metric
Metrics to use

A. Exact Match / F1
Use when answers are short and standardized.

B. Semantic correctness
Use LLM-as-judge or semantic similarity if answers are longer and phrased differently.

C. Answer relevance
Checks whether the answer actually addresses the question.

Ragas provides Answer Relevancy / Response Relevancy, and DeepEval provides Answer Relevancy. Phoenix also supports QA evaluation workflows for retrieved-data Q&A.

## test grounding and hallucination separately
Metrics to use

A. Faithfulness / Groundedness
Does the answer stay supported by retrieved context?

Ragas defines Faithfulness as factual consistency between response and retrieved context. LangSmith’s RAG evaluation tutorial includes groundedness checks against retrieved docs. DeepEval also has a Faithfulness metric for RAG output vs retrieval context.

B. Unsupported claim rate
Count answers that include facts not in retrieved chunks.

C. Citation support rate
If your bot cites sources, check whether the cited chunk actually supports the claim.

Minimum practical target

For a small public-benchmark proof:

grounding should be consistently strong
hallucination should be rare
unsupported claims should be easy to explain and debug

## add an abstention test
You want some questions where the system should not answer confidently.

How to do it with public data

Create a tiny negative set from the same benchmark:

ask a question about a document that was not ingested
ask a question with an entity swap
ask a question whose answer is absent from the retrieved context

Then score:

did it abstain?
did it say “not enough information”?
did it hallucinate anyway?

This is one of the fastest ways to show real-world safety and robustness.

## Step 9, measure latency and consistency
Even a correct RAG system is not deployment-ready if it is too slow or unstable.

Track:

end-to-end latency
retrieval latency
generation latency
token usage / cost
error rate / timeout rate

For a small benchmark, report:

p50 latency
p95 latency
average cost per question

LangChain, LangSmith

# Other

This folder contains a runnable script to evaluate the backend RAG chatbot through the live API flow:

1. log in and get a JWT from `/auth/token`
2. optionally reset the backend with `/admin/reset`
3. ingest benchmark contexts through `/ingest/text`
4. ask benchmark questions through `/chat` with `debug=true`
5. score the results with RAGAS
6. produce a compact summary with retrieval, generation, and operational metrics

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r eval\requirements.txt
```

## Evaluator model

RAGAS metrics need judge models.

- For LLM-based metrics, provide an OpenAI-compatible judge model with `--eval-llm-model`.
- For embedding-based metrics, provide an OpenAI-compatible embedding endpoint with `--eval-embedding-model`.
- If you only provide neither, the script still runs the non-LLM retrieval metric `NonLLMContextPrecisionWithReference`.

Examples:

- OpenAI:

```powershell
$env:OPENAI_API_KEY="sk-..."
python eval\ragas_eval.py --base-url http://localhost:9010 --eval-llm-model gpt-4o-mini --eval-embedding-model text-embedding-3-small
```

- Local OpenAI-compatible endpoint such as vLLM or Ollama:

```powershell
python eval\ragas_eval.py `
  --base-url http://localhost:9010 `
  --eval-llm-model llama3.1:8b `
  --eval-llm-base-url http://localhost:11434/v1 `
  --eval-embedding-model nomic-embed-text `
  --eval-embedding-base-url http://localhost:11434/v1
```

## Dataset options

### Option 1: Hugging Face dataset

The default dataset is the Amnesty QA benchmark used in RAGAS documentation.

```powershell
python eval\ragas_eval.py `
  --base-url http://localhost:9010 `
  --reset-first `
  --limit 10 `
  --eval-llm-model gpt-4o-mini `
  --eval-embedding-model text-embedding-3-small
```

You can override the dataset:

```powershell
python eval\ragas_eval.py `
  --dataset-source huggingface `
  --hf-dataset explodinggradients/amnesty_qa `
  --hf-config english_v3 `
  --hf-split eval
```

### Option 2: Local JSONL benchmark

Each line should contain at least:

```json
{
  "id": "sample-1",
  "question": "What does the policy say about refunds?",
  "ground_truth": "Refunds are allowed within 30 days with proof of purchase.",
  "reference_contexts": [
    "Refunds are allowed within 30 days with proof of purchase."
  ]
}
```

Run it with:

```powershell
python eval\ragas_eval.py `
  --dataset-source jsonl `
  --dataset-path .\eval\my-benchmark.jsonl `
  --base-url http://localhost:9010 `
  --reset-first `
  --limit 25 `
  --eval-llm-model gpt-4o-mini `
  --eval-embedding-model text-embedding-3-small
```

## Output

Each run writes to `eval/output/<timestamp>/`:

- `config.json`
- `summary.json`
- `backend_results.jsonl`
- `ragas_scored_results.jsonl`
- `ragas_scored_results.csv`

`summary.json` is now grouped into:

- `operational`: answer rate, fallback rate, retrieval hit rate, average retrieved contexts, citations, and ingest counts
- `retrieval`: RAGAS retrieval metrics plus a lexical context-match rate against the benchmark contexts
- `generation`: RAGAS answer metrics plus a lexical answer-match rate and a blended quality score
- `weakest_samples`: the lowest-quality examples so you can inspect failures quickly

## Metrics

The script uses these RAGAS metrics when the required judge models are available:

- `NonLLMContextPrecisionWithReference`
- `Faithfulness` when a judge LLM is configured
- `ResponseRelevancy` when a judge LLM is configured
- `LLMContextRecall` when a judge LLM is configured
- `FactualCorrectness` when a judge LLM is configured
- `SemanticSimilarity` when judge embeddings are configured

It also derives lightweight operational metrics that are useful even when judge coverage is limited:

- retrieval hit rate
- fallback rate
- average retrieved contexts and citations
- lexical context match against the reference contexts
- lexical answer similarity against the ground truth
- a per-sample `quality_score` blended from the available answer-quality metrics

## Notes

- `--reset-first` deletes backend state. Use it only on a safe environment.
- The script ingests unique benchmark contexts only once, deduplicated by content hash.
- The backend must expose retrieved chunks on `/chat` when `debug=true`, which this project already does.
