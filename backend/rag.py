"""
Retrieval-Augmented Generation: find the policy rules relevant to a call.

How it works
------------
1. Indexing: every rule from policy.txt is embedded with Pinecone's hosted
   embedding model and stored in a Pinecone index. Vectors live in a namespace
   named after the policy version (a hash of policy.txt), so editing the
   policy automatically produces a fresh, consistent set of vectors.
2. Retrieval: the call transcript is split into short windows of a few
   dialogue turns. Each window is embedded and the closest rules are looked
   up. The union of those rules is what the LLM checks the call against.
3. Safety net: zero-tolerance rules are always checked, even if retrieval did
   not pick them, because missing one of them would hide a critical breach.

If Pinecone is not configured or is unreachable, every rule is returned. The
audit still works; it just checks all rules instead of the relevant ones.
"""

import logging
import time

from backend import config
from backend.policy import PolicyRule, load_policy_rules, policy_version

logger = logging.getLogger(__name__)

TURNS_PER_WINDOW = 6     # dialogue lines per retrieval query
RULES_PER_WINDOW = 3     # nearest rules fetched for each window


class PolicyRetriever:
    def __init__(self):
        self.rules = load_policy_rules()
        self.rules_by_id = {rule.rule_id: rule for rule in self.rules}
        self.namespace = f"policy-{policy_version()}"
        self._index = None
        self._pinecone = None

    # ----- public API ----------------------------------------------------

    def relevant_rules(self, transcript: str) -> list[PolicyRule]:
        """Return the rules the LLM should check this transcript against."""
        if not config.PINECONE_API_KEY:
            logger.warning("PINECONE_API_KEY not set — checking the call against all policy rules.")
            return self.rules

        try:
            retrieved_ids = self._retrieve_rule_ids(transcript)
        except Exception:
            logger.exception("Policy retrieval failed — checking the call against all policy rules.")
            return self.rules

        if not retrieved_ids:
            return self.rules

        always_checked = {rule.rule_id for rule in self.rules if rule.zero_tolerance}
        selected_ids = retrieved_ids | always_checked
        # Keep the policy's own order so prompts are stable and easy to read.
        return [rule for rule in self.rules if rule.rule_id in selected_ids]

    # ----- retrieval -----------------------------------------------------

    def _retrieve_rule_ids(self, transcript: str) -> set[str]:
        windows = split_into_windows(transcript, TURNS_PER_WINDOW)
        if not windows:
            return set()

        index = self._get_index()
        query_vectors = self._embed(windows, input_type="query")

        rule_ids = set()
        for vector in query_vectors:
            result = index.query(
                namespace=self.namespace,
                vector=vector,
                top_k=RULES_PER_WINDOW,
                include_metadata=False,
            )
            rule_ids.update(match["id"] for match in result["matches"])

        # Ignore any IDs that are no longer in the policy.
        return rule_ids & self.rules_by_id.keys()

    # ----- indexing ------------------------------------------------------

    def _get_index(self):
        """Connect to the Pinecone index, creating and filling it on first use."""
        if self._index is not None:
            return self._index

        from pinecone import Pinecone, ServerlessSpec

        self._pinecone = Pinecone(api_key=config.PINECONE_API_KEY)
        index_name = config.PINECONE_INDEX_NAME

        if index_name not in self._pinecone.list_indexes().names():
            logger.info("Creating Pinecone index '%s'...", index_name)
            self._pinecone.create_index(
                name=index_name,
                dimension=config.PINECONE_EMBED_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
            )
            self._wait_until_ready(index_name)

        index = self._pinecone.Index(index_name)
        if self._namespace_vector_count(index) < len(self.rules):
            self._upload_rules(index)

        self._index = index
        return index

    def _upload_rules(self, index):
        logger.info("Indexing %d policy rules into namespace '%s'...", len(self.rules), self.namespace)
        vectors = self._embed([rule.as_prompt_text() for rule in self.rules], input_type="passage")
        index.upsert(
            namespace=self.namespace,
            vectors=[
                {"id": rule.rule_id, "values": vector, "metadata": {"title": rule.title}}
                for rule, vector in zip(self.rules, vectors)
            ],
        )
        # Pinecone is eventually consistent; wait briefly so the first query sees the rules.
        for _ in range(10):
            if self._namespace_vector_count(index) >= len(self.rules):
                break
            time.sleep(1)

    def _namespace_vector_count(self, index) -> int:
        namespaces = index.describe_index_stats().get("namespaces", {})
        return namespaces.get(self.namespace, {}).get("vector_count", 0)

    def _wait_until_ready(self, index_name: str, timeout_seconds: int = 60):
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._pinecone.describe_index(index_name).status["ready"]:
                return
            time.sleep(2)
        raise TimeoutError(f"Pinecone index '{index_name}' was not ready after {timeout_seconds}s")

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        """Embed texts with Pinecone's hosted model. input_type is 'passage' or 'query'."""
        if self._pinecone is None:
            from pinecone import Pinecone
            self._pinecone = Pinecone(api_key=config.PINECONE_API_KEY)

        response = self._pinecone.inference.embed(
            model=config.PINECONE_EMBED_MODEL,
            inputs=texts,
            parameters={"input_type": input_type, "truncate": "END"},
        )
        return [item["values"] for item in response]


def split_into_windows(transcript: str, lines_per_window: int) -> list[str]:
    """Group non-empty transcript lines into consecutive windows."""
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    return [
        "\n".join(lines[start:start + lines_per_window])
        for start in range(0, len(lines), lines_per_window)
    ]


_retriever = None


def get_retriever() -> PolicyRetriever:
    """Shared retriever, created on first use so the app starts fast."""
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever()
    return _retriever
