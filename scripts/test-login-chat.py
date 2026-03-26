#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import mimetypes
import uuid
from pathlib import Path
from urllib import error, request


CHAT_MESSAGE = "How can I collaborate with SNAIC?"
DOCX_FILENAME = "FOR SNAIC CHATBOT INGESTION_SNAIC Overview.docx"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def http_request(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )

    try:
        with request.urlopen(req, timeout=120) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc


def http_post_multipart(
    url: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    body_parts: list[bytes] = []

    for name, value in fields.items():
        body_parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    file_bytes = file_path.read_bytes()
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body_parts.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8"),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )

    req = request.Request(
        url=url,
        data=b"".join(body_parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **(headers or {})},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=120) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc


def http_stream_events(
    url: str,
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
) -> list[tuple[str, dict[str, object]]]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )

    events: list[tuple[str, dict[str, object]]] = []
    try:
        with request.urlopen(req, timeout=120) as resp:
            current_event: str | None = None
            current_data: list[str] = []

            while True:
                raw_line = resp.readline()
                if not raw_line:
                    break

                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    if current_event is not None:
                        data_text = "\n".join(current_data).strip()
                        events.append((current_event, json.loads(data_text) if data_text else {}))
                    current_event = None
                    current_data = []
                    continue

                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    continue

                if line.startswith("data: "):
                    current_data.append(line[6:])
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc

    return events


def print_retrieved_chunks(label: str, response_payload: dict[str, object]) -> None:
    retrieved_chunks = response_payload.get("retrieved_chunks", [])
    if not isinstance(retrieved_chunks, list):
        return

    print(f"{label} RETRIEVED CHUNKS:")
    for index, chunk in enumerate(retrieved_chunks, start=1):
        if not isinstance(chunk, dict):
            continue
        title = chunk.get("title")
        score = chunk.get("similarity_score")
        chunk_index = (chunk.get("metadata") or {}).get("chunk_index")
        print(f"{index}. title={title!r} score={score} chunk_index={chunk_index}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / "backend" / ".env"
    env = load_env_file(env_path)

    base_url = os.environ.get("BASE_URL", f"http://localhost:{env.get('APP_PORT', '9010')}")
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = f"http://{base_url}"

    username = env.get("AUTH_BOOTSTRAP_ADMIN_USERNAME", "admin")
    password = env.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not password:
        raise RuntimeError("AUTH_BOOTSTRAP_ADMIN_PASSWORD is empty in backend/.env")

    token_response = http_request(
        "POST",
        f"{base_url}/auth/token",
        {"username": username, "password": password},
    )
    token = token_response.get("access_token")
    if not token or not isinstance(token, str):
        raise RuntimeError(f"Login succeeded but no access_token was returned: {token_response}")

    headers = {"Authorization": f"Bearer {token}"}

    docx_path = repo_root / "scripts" / DOCX_FILENAME
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    ingest_response = http_post_multipart(
        f"{base_url}/ingest/files",
        fields={"force_reingest": "true"},
        file_field="files",
        file_path=docx_path,
        headers=headers,
    )
    print("INGEST RESPONSE:")
    print(json.dumps(ingest_response, indent=2, ensure_ascii=False))

    chat_response = http_request(
        "POST",
        f"{base_url}/chat",
        {"message": CHAT_MESSAGE, "debug": True},
        headers=headers,
    )
    print("CHAT RESPONSE:")
    print(json.dumps(chat_response, indent=2, ensure_ascii=False))
    print_retrieved_chunks("CHAT", chat_response)

    stream_events = http_stream_events(
        f"{base_url}/chat/stream",
        {"message": CHAT_MESSAGE, "debug": True},
        headers=headers,
    )
    done_payload = {}
    for event_name, event_data in stream_events:
        if event_name == "done":
            done_payload = event_data
            break

    print("CHAT STREAM DONE:")
    print(json.dumps(done_payload, indent=2, ensure_ascii=False))
    print_retrieved_chunks("CHAT STREAM", done_payload)


if __name__ == "__main__":
    main()
