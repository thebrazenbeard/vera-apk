"""Optional authenticated V2 Vera inbox HTTP receive/ack endpoints.

Unlike the legacy response-only gateway, this is a strictly owner-approved
inbox consumer. No HTTP enqueue or model-origin signing route exists.

This is a SOURCE/TEST candidate, not a production process or phone push.
"""
from __future__ import annotations

from device_gateway_v2 import DeviceHandler, DeviceServer
from device_scoped_history import AccessDenied as DeviceAccessDenied, InvalidRequest
from owner_outbox_v0 import (
    AccessDenied as InboxAccessDenied, InvalidEnvelope,
    StorageFailure,
)


class InboxDeviceServer(DeviceServer):
    def __init__(self, address, store, outbox):
        if outbox is None:
            raise ValueError("inbox store required")
        self.inbox = outbox
        super().__init__(address, store, handler=InboxDeviceHandler)


class InboxDeviceHandler(DeviceHandler):
    def do_GET(self):
        if self.path != "/v2/inbox":
            return super().do_GET()
        try:
            token = self.authenticate()
            # Validate active owner+device before any inbox offer. A session ID
            # alone is never authentication and shared V1 bearers are refused.
            self.server.store.authenticate(token)
            messages = self.server.inbox.poll(token, limit=5)
            return self.response(200, {
                "schema": "vera.inbox.v1",
                "origin": "vera_host_approved",
                "node": "local",
                "messages": messages,
            })
        except (DeviceAccessDenied, InboxAccessDenied):
            return self.response(403, {"error": "forbidden"})
        except (InvalidRequest, InvalidEnvelope, ValueError):
            return self.response(400, {"error": "invalid request"})
        except (StorageFailure, OSError, Exception):
            return self.response(503, {"error": "unavailable"})

    def do_POST(self):
        if self.path != "/v2/inbox/ack":
            return super().do_POST()
        try:
            token = self.authenticate()
            self.server.store.authenticate(token)
            data = self._body()
            if type(data) is not dict or set(data) != {"message_id"}:
                raise InvalidRequest("exact ack schema required")
            result = self.server.inbox.ack(token, data["message_id"])
            return self.response(200, {
                "schema": "vera.inbox.ack.v1",
                "origin": "vera_host_approved",
                **result,
            })
        except (DeviceAccessDenied, InboxAccessDenied):
            return self.response(403, {"error": "forbidden"})
        except (InvalidRequest, InvalidEnvelope, ValueError, TypeError):
            return self.response(400, {"error": "invalid request"})
        except (StorageFailure, OSError, Exception):
            return self.response(503, {"error": "unavailable"})
