"""A custom DataHub Action: POST an alert to a webhook when a Paper Trail
review tag changes on an asset (confirmed / risk-flagged / rejected).

This runs inside the datahub-actions container on DataHub's own event stream
(Kafka EntityChangeEvents), so it demonstrates DataHub *acting* on an event --
the metadata graph as a nervous system, not a passive logbook. The target URL
comes from config or the PT_WEBHOOK_URL env var; nothing secret is hard-coded.
"""
import os

import requests
from datahub_actions.action.action import Action
from datahub_actions.event.event_envelope import EventEnvelope
from datahub_actions.pipeline.pipeline_context import PipelineContext

# Only these review-tag changes are worth alerting on.
ALERT_TAGS = ("confirmed", "risk-flagged", "rejected", "pending-review")


class WebhookAction(Action):
    def __init__(self, config: dict, ctx: PipelineContext):
        self.url = (config or {}).get("url") or os.environ.get(
            "PT_WEBHOOK_URL", "http://host.docker.internal:8757/hook")
        print(f"[pt-webhook] action ready -> {self.url}", flush=True)

    @classmethod
    def create(cls, config_dict: dict, ctx: PipelineContext) -> "WebhookAction":
        return cls(config_dict or {}, ctx)

    def act(self, event: EventEnvelope) -> None:
        ev = getattr(event, "event", None)

        def g(attr):
            try:
                return getattr(ev, attr, None)
            except Exception:
                return None

        category = g("category")
        modifier = g("modifier") or ""
        # Only alert on our review-tag lifecycle events.
        if category != "TAG" or not any(t in modifier for t in ALERT_TAGS):
            return
        payload = {
            "source": "datahub-actions",
            "event_type": getattr(event, "event_type", None),
            "entityUrn": g("entityUrn"),
            "category": category,
            "operation": g("operation"),
            "modifier": modifier,
        }
        try:
            requests.post(self.url, json=payload, timeout=5)
            print(f"[pt-webhook] POST {payload}", flush=True)
        except Exception as e:
            print(f"[pt-webhook] error: {e}", flush=True)

    def close(self) -> None:
        pass
