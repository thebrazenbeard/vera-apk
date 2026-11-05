package com.vera.companion;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import javax.net.ssl.HttpsURLConnection;

/** Bounded response-only transport. No redirects, cleartext, tool calls, or remote actions. */
public final class GatewayClient {
    private GatewayClient() {}

    /** An upstream completion receipt, not proof of model cognition or identity. */
    public static final class ChatReply {
        public final String text;
        public final String completionStatus;
        public final Boolean truncated;
        public final Boolean incomplete;
        public final boolean personaConfigured;

        private ChatReply(String text, String completionStatus, Boolean truncated,
                          Boolean incomplete, boolean personaConfigured) {
            this.text = text;
            this.completionStatus = completionStatus;
            this.truncated = truncated;
            this.incomplete = incomplete;
            this.personaConfigured = personaConfigured;
        }
    }

    private static JSONObject request(String base, String token, String path, JSONObject body)
            throws Exception {
        String endpoint = EndpointPolicy.normalize(base);
        if (token == null || !token.matches("[A-Za-z0-9_-]{32,128}")) {
            throw new IllegalArgumentException("Pairing token required");
        }
        HttpsURLConnection connection = (HttpsURLConnection)
                new URL(endpoint + path).openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(95000);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/json");
        connection.setUseCaches(false);
        try {
            if (body != null) {
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                if (payload.length > 32768) throw new IllegalArgumentException("Chat too long");
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setFixedLengthStreamingMode(payload.length);
                try (OutputStream out = connection.getOutputStream()) { out.write(payload); }
            }
            int status = connection.getResponseCode();
            if (status != 200) throw new IllegalStateException("Gateway returned HTTP " + status);
            String type = connection.getContentType();
            if (type == null || !type.toLowerCase(java.util.Locale.ROOT).startsWith("application/json"))
                throw new IllegalStateException("Gateway returned unexpected content type");
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (InputStream in = connection.getInputStream()) {
                byte[] chunk = new byte[4096]; int n;
                while ((n = in.read(chunk)) != -1) {
                    if (output.size() + n > 65536) throw new IllegalStateException("Gateway response too long");
                    output.write(chunk, 0, n);
                }
            }
            return new JSONObject(new String(output.toByteArray(), StandardCharsets.UTF_8));
        } finally {
            connection.disconnect();
        }
    }

    public static List<String> models(String base, String token) throws Exception {
        JSONArray array = request(base, token, "/v1/models", null).getJSONArray("models");
        List<String> found = new ArrayList<>();
        for (int i = 0; i < array.length() && i < 32; i++) {
            String model = array.getString(i);
            if (!model.isEmpty() && model.length() <= 128) found.add(model);
        }
        return found;
    }

    public static String chat(String base, String token, String model, JSONArray history,
                              String sessionId, String requestId) throws Exception {
        return chatWithReceipt(base, token, model, history, sessionId, requestId).text;
    }

    public static ChatReply chatWithReceipt(String base, String token, String model,
                                            JSONArray history, String sessionId,
                                            String requestId) throws Exception {
        JSONObject body = new JSONObject();
        body.put("model", model);
        body.put("messages", history);
        body.put("session_id", sessionId);
        body.put("request_id", requestId);
        JSONObject result = request(base, token, "/v1/chat", body);
        if (!"response_only".equals(result.optString("mode"))) {
            throw new IllegalStateException("Gateway authority mismatch");
        }
        String reply = result.getString("reply");
        if (reply.length() > 16000) throw new IllegalStateException("Response too long");
        if (!result.has("response_completion_status")) {
            if (result.has("persona_source") || result.has("response_incomplete")
                    || result.has("response_truncated")) {
                throw new IllegalStateException("Partial completion receipt");
            }
            return new ChatReply(reply, "not_reported", null, null, false);
        }
        String completion = result.getString("response_completion_status");
        if (!completion.equals("complete") && !completion.equals("length_limited")
                && !completion.equals("filtered") && !completion.equals("unknown")) {
            throw new IllegalStateException("Unsupported completion status");
        }
        Object incompleteRaw = result.get("response_incomplete");
        Object truncatedRaw = result.get("response_truncated");
        Boolean incomplete = incompleteRaw == JSONObject.NULL ? null
                : incompleteRaw instanceof Boolean ? (Boolean) incompleteRaw : null;
        Boolean truncated = truncatedRaw == JSONObject.NULL ? null
                : truncatedRaw instanceof Boolean ? (Boolean) truncatedRaw : null;
        if ((incompleteRaw != JSONObject.NULL && !(incompleteRaw instanceof Boolean))
                || (truncatedRaw != JSONObject.NULL && !(truncatedRaw instanceof Boolean))
                || (completion.equals("complete") && (!Boolean.FALSE.equals(incomplete)
                    || !Boolean.FALSE.equals(truncated)))
                || (completion.equals("length_limited") && (!Boolean.TRUE.equals(incomplete)
                    || !Boolean.TRUE.equals(truncated)))
                || (completion.equals("filtered") && (!Boolean.TRUE.equals(incomplete)
                    || !Boolean.FALSE.equals(truncated)))
                || (completion.equals("unknown") && (incomplete != null || truncated != null))) {
            throw new IllegalStateException("Inconsistent completion receipt");
        }
        JSONObject persona = result.getJSONObject("persona_source");
        if (!"SOURCE_ONLY".equals(persona.optString("qualification"))
                || !"server_owned_system".equals(persona.optString("prompt_layer"))
                || persona.optBoolean("trained_weights_modified", true)
                || persona.optBoolean("identity_attested", true)) {
            throw new IllegalStateException("Persona configuration not verified");
        }
        return new ChatReply(reply, completion, truncated, incomplete, true);
    }
}
