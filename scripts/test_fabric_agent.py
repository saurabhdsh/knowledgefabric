import json
import sys
import urllib.error
import urllib.request


API_BASE = "http://localhost:8000/api/v1"


def api_get(path: str) -> dict:
    req = urllib.request.Request(f"{API_BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pick_fabric_id() -> str:
    response = api_get("/knowledge/")
    items = response.get("data") or []
    if not items:
        raise RuntimeError("No fabrics available to test.")
    return items[0]["id"]


def run_agent_query(fabric_id: str, query: str) -> dict:
    return api_post(
        f"/knowledge/query/{fabric_id}",
        {"query": query, "llm_provider": "openai"},
    )


def main() -> int:
    try:
        fabric_id = pick_fabric_id()
        query = "Summarize the key requirements in this fabric."
        result = run_agent_query(fabric_id, query)
        print("Fabric ID:", fabric_id)
        print("Success:", result.get("success"))
        print("Message:", result.get("message"))
        data = result.get("data") or {}
        print("Confidence:", data.get("confidence"))
        print("Relevant Chunks:", data.get("relevant_chunks"))
        print("\nAgent Answer:\n")
        print(data.get("answer", "<no answer>"))
        return 0 if result.get("success") else 1
    except urllib.error.HTTPError as http_err:
        body = http_err.read().decode("utf-8", errors="replace")
        print(f"HTTP error: {http_err.code} {http_err.reason}")
        print(body)
        return 2
    except Exception as exc:
        print(f"Agent test failed: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
