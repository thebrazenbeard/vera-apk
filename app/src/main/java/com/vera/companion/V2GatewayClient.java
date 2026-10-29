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
        if (!enabled(base)) throw new IllegalArgumentException("V2 requires dedicated :8444 endpoint");
        if (payload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 8192)
            throw new IllegalArgumentException("V2 request exceeds limit");
        return GatewayClient.request(base, token, path, payload, status);
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
        String id = post(base,token,"/v2/sessions",new JSONObject(),201).getString("session_id");
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
        if (!sessionId.matches("[A-Za-z0-9_-]{16,128}")
                || !requestId.matches("[A-Za-z0-9_-]{16,128}")
                || text.isEmpty() || text.length()>4096 || model.length()>128)
            throw new IllegalArgumentException("Invalid V2 request");
        JSONObject body = new JSONObject()
                .put("session_id",sessionId).put("request_id",requestId)
                .put("model",model).put("content",text);
        JSONObject result=post(base,token,"/v2/chat",body,200);
        if (!"local".equals(result.optString("node"))
                || !"response_only".equals(result.optString("mode"))
                || !model.equals(result.optString("model")))
            throw new IllegalStateException("Unexpected V2 response");
        String reply=result.getString("reply");
        if (reply.isEmpty() || reply.length()>16000) throw new IllegalStateException("Invalid reply");
        return reply;
    }
}
