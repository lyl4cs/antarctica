"""Job queue abstraction.

HOW IT WORKS
The API never runs Lighthouse itself (see docs/DECISIONS.md #001). It publishes a
small JSON job to a Pub/Sub topic. Pub/Sub then PUSHES that message as an HTTP POST
to the scanner service on Cloud Run. If the scanner returns 2xx the message is
acked; any other status means "retry later". After N failed deliveries, Pub/Sub
moves it to the dead-letter topic.

The Publisher protocol lets tests use an in-memory fake, so tests never need GCP.
"""

from __future__ import annotations

import json
from typing import Protocol


class Publisher(Protocol):
    def publish(self, job: dict) -> str: ...


class InMemoryPublisher:
    def __init__(self) -> None:
        self.jobs: list[dict] = []

    def publish(self, job: dict) -> str:
        self.jobs.append(job)
        return str(len(self.jobs))


class PubSubPublisher:  # pragma: no cover - needs GCP
    def __init__(self, project_id: str, topic: str) -> None:
        from google.cloud import pubsub_v1

        self._client = pubsub_v1.PublisherClient()
        self._topic = self._client.topic_path(project_id, topic)

    def publish(self, job: dict) -> str:
        future = self._client.publish(self._topic, json.dumps(job).encode())
        return future.result(timeout=10)
