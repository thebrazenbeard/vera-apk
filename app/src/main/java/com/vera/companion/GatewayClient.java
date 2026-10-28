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
        return reply;
    }
}
