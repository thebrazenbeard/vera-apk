package com.vera.companion;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;

/** Explicit :8444 V2 client. Never downgrades to shared-token V1. */
public final class V2GatewayClient {
    private V2GatewayClient() {}

    public static boolean enabled(String endpoint) {
        return EndpointPolicy.isV2(endpoint);
    }

    private static JSONObject get(String base, String token, String path) throws Exception {
        if (!enabled(base)) throw new IllegalArgumentException("V2 requires dedicated :8444 endpoint");
        return GatewayClient.request(base, token, path, null);
    }

    private static JSONObject post(String base, String token, String path, JSONObject payload,
                                   int status) throws Exception {
        return post(base, token, path, payload, status, null, 0L);
    }

    private static JSONObject post(String base, String token, String path, JSONObject payload,
                                   int status, PairingEpoch pairing, long generation)
            throws Exception {
        if (!enabled(base)) throw new IllegalArgumentException("V2 requires dedicated :8444 endpoint");
        if (payload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 8192)
            throw new IllegalArgumentException("V2 request exceeds limit");
        return GatewayClient.request(base, token, path, payload, status, pairing, generation);
    }

    public static List<String> models(String base, String token) throws Exception {
        JSONObject response = get(base, token, "/v2/models");
        if (!"local".equals(response.optString("node"))
                || !"response_only".equals(response.optString("mode")))
            throw new IllegalStateException("Unexpected V2 authority");
        JSONArray array = response.getJSONArray("models");
        if (array.length() > 32) throw new IllegalStateException("Invalid model count");
        List<String> result = new ArrayList<>();
        for (int i=0; i<array.length(); i++) {
            String name = array.getString(i);
            if (name.isEmpty() || name.length()>128) throw new IllegalStateException("Invalid model");
            result.add(name);
        }
        return result;
    }

    public static List<String> sessions(String base, String token) throws Exception {
        JSONArray array = get(base, token, "/v2/sessions").getJSONArray("sessions");
        if (array.length()>50) throw new IllegalStateException("Unbounded session list");
        List<String> result = new ArrayList<>();
        for (int i=0; i<array.length(); i++) {
            String id = array.getString(i);
            if (!id.matches("[A-Za-z0-9_-]{16,128}")) throw new IllegalStateException("Invalid session ID");
            result.add(id);
        }
        return result;
    }

    public static String createSession(String base, String token) throws Exception {
        return createSession(base, token, null, 0L);
    }

    static String createSession(String base, String token, PairingEpoch pairing,
                                long generation) throws Exception {
        String id = post(base,token,"/v2/sessions",new JSONObject(),201,pairing,generation)
                .getString("session_id");
        if (!id.matches("[A-Za-z0-9_-]{16,128}")) throw new IllegalStateException("Invalid issued session");
        return id;
    }

    public static JSONArray history(String base, String token, String sessionId) throws Exception {
        if (sessionId==null || !sessionId.matches("[A-Za-z0-9_-]{16,128}"))
            throw new IllegalArgumentException("Invalid session");
        JSONObject result = get(base, token, "/v2/sessions/" + sessionId + "/history");
        if (!sessionId.equals(result.getString("session_id")))
            throw new IllegalStateException("Wrong session returned");
        JSONArray turns = result.getJSONArray("turns");
        if (turns.length()>20) throw new IllegalStateException("Unbounded history");
        for (int i=0;i<turns.length();i++) {
            JSONObject item=turns.getJSONObject(i);
            if (item.getString("user").length()>4096
                    || item.getString("assistant").length()>16000)
                throw new IllegalStateException("Unbounded history content");
        }
        return turns;
    }

    public static String chat(String base, String token, String model,
                              String sessionId, String requestId, String text) throws Exception {
        return chat(base, token, model, sessionId, requestId, text, null, 0L);
    }

    static String chat(String base, String token, String model,
                       String sessionId, String requestId, String text,
                       PairingEpoch pairing, long generation) throws Exception {
        if (!sessionId.matches("[A-Za-z0-9_-]{16,128}")
                || !requestId.matches("[A-Za-z0-9_-]{16,128}")
                || text.isEmpty() || text.length()>4096 || model.length()>128)
            throw new IllegalArgumentException("Invalid V2 request");
        JSONObject body = new JSONObject()
                .put("session_id",sessionId).put("request_id",requestId)
                .put("model",model).put("content",text);
        JSONObject result=post(base,token,"/v2/chat",body,200,pairing,generation);
        if (!"local".equals(result.optString("node"))
                || !"response_only".equals(result.optString("mode"))
                || !model.equals(result.optString("model")))
            throw new IllegalStateException("Unexpected V2 response");
        String reply=result.getString("reply");
        if (reply.isEmpty() || reply.length()>16000) throw new IllegalStateException("Invalid reply");
        return reply;
    }

    /** HTTPS V2 device-only foreground inbox. No V1 fallback, no sender action. */
    public static List<VeraInboxMessage> inbox(String base, String token) throws Exception {
        JSONObject wire = get(base, token, "/v2/inbox");
        if (!VeraInboxMessage.authorizedEnvelope(
                wire.optString("schema"), wire.optString("origin"),
                wire.optString("node")))
            throw new IllegalStateException("Unexpected inbox source");
        JSONArray messages = wire.getJSONArray("messages");
        if (messages.length() > 5)
            throw new IllegalStateException("Unbounded incoming batch");
        long now = System.currentTimeMillis() / 1000L;
        List<VeraInboxMessage> result = new ArrayList<>();
        java.util.HashSet<String> ids = new java.util.HashSet<>();
        for (int i=0; i<messages.length(); i++) {
            JSONObject item = messages.getJSONObject(i);
            if (item.length()!=6 || !item.has("message_id") || !item.has("kind")
                    || !item.has("body") || !item.has("expires_at")
                    || !item.has("offer_attempt") || !item.has("state"))
                throw new IllegalStateException("Invalid incoming schema");
            if (!"OFFERED_NOT_DELIVERED".equals(item.getString("state")))
                throw new IllegalStateException("Unverified delivery state");
            Object expiration = item.get("expires_at");
            Object attempt = item.get("offer_attempt");
            if (!(expiration instanceof Number) || !(attempt instanceof Number))
                throw new IllegalStateException("Invalid incoming metadata");
            VeraInboxMessage msg = new VeraInboxMessage(
                    item.getString("message_id"),
                    item.getString("body"), item.getString("kind"),
                    ((Number)expiration).longValue(),
                    ((Number)attempt).intValue(), now);
            if (!ids.add(msg.messageId))
                throw new IllegalStateException("Duplicate message ID in batch");
            result.add(msg);
        }
        return result;
    }

    /** Acknowledges durable device receipt, not human reading of the message. */
    public static void acknowledgeInbox(
            String base, String token, String messageId) throws Exception {
        acknowledgeInbox(base, token, messageId, null, 0L);
    }

    static void acknowledgeInbox(String base, String token, String messageId,
                                 PairingEpoch pairing, long generation) throws Exception {
        if (messageId == null || !messageId.matches("[a-f0-9]{32}"))
            throw new IllegalArgumentException("Invalid acknowledgment id");
        JSONObject response = post(base, token, "/v2/inbox/ack",
                new JSONObject().put("message_id", messageId), 200, pairing, generation);
        if (!VeraInboxMessage.validAck(
                response.optString("schema"), response.optString("origin"),
                response.optString("message_id"), messageId,
                response.optString("state")))
            throw new IllegalStateException("Acknowledgment authority mismatch");
    }

}
