package com.vera.companion;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Keystore AES-GCM encrypted, device-pairing-bound persistent V2 inbox.
 * No plaintext message body is placed in preferences. No backup is permitted.
 */
public final class SecureVeraInbox {
    private static final String PREFS = "vera_approved_inbox_v0";
    private static final String KEY = "vera.inbox.keystore.v0";
    private static final int MAX_RECORDS = 32;
    private SecureVeraInbox() {}

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        SecretKey existing = (SecretKey) store.getKey(KEY, null);
        if (existing != null) return existing;
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return generator.generateKey();
    }

    private static byte[] binding(String endpoint, String token) throws Exception {
        if (!V2GatewayClient.enabled(endpoint) || token == null
                || !token.matches("[A-Za-z0-9_-]{32,128}"))
            throw new SecurityException("V2 device pairing required");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        return hash.digest(("VERA_INBOX_V0" + (char)0 + endpoint + (char)0 + token)
                .getBytes(StandardCharsets.UTF_8));
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static JSONArray decrypt(Context context, String endpoint,
                                     String token) throws Exception {
        SharedPreferences p = prefs(context);
        String data = p.getString("ciphertext", null);
        String iv = p.getString("iv", null);
        if (data == null && iv == null) return new JSONArray();
        if (data == null || iv == null)
            throw new SecurityException("Incomplete encrypted inbox");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(),
                new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
        cipher.updateAAD(binding(endpoint, token));
        byte[] plain = cipher.doFinal(Base64.decode(data, Base64.NO_WRAP));
        if (plain.length > 160000)
            throw new SecurityException("Encrypted inbox exceeds storage bound");
        JSONArray messages = new JSONArray(new String(plain, StandardCharsets.UTF_8));
        if (messages.length() > MAX_RECORDS)
            throw new SecurityException("Unbounded encrypted inbox");
        return messages;
    }

    private static void save(Context context, String endpoint, String token,
                             JSONArray array) throws Exception {
        if (array.length() > MAX_RECORDS)
            throw new IllegalArgumentException("Unbounded inbox");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        cipher.updateAAD(binding(endpoint, token));
        byte[] payload = cipher.doFinal(array.toString().getBytes(StandardCharsets.UTF_8));
        if (!prefs(context).edit()
                .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("ciphertext", Base64.encodeToString(payload, Base64.NO_WRAP))
                .commit())
            throw new SecurityException("Inbox persistence failed");
    }

    private static VeraInboxMessage decode(JSONObject item, long now) throws Exception {
        return VeraInboxMessage.fromEncryptedStore(
                item.getString("message_id"), item.getString("body"),
                item.getString("kind"), item.getLong("expires_at"),
                item.optInt("offer_attempt", 1), now);
    }

    public static synchronized List<VeraInboxMessage> read(
            Context context, String endpoint, String token) throws Exception {
        long now = System.currentTimeMillis() / 1000;
        JSONArray values = decrypt(context, endpoint, token);
        List<VeraInboxMessage> found = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (int i=0; i<values.length(); i++) {
            JSONObject item = values.getJSONObject(i);
            VeraInboxMessage msg = decode(item, now);
            if (!seen.add(msg.messageId))
                throw new SecurityException("Duplicate stored inbound ID");
            found.add(msg);
        }
        return found;
    }

    /** Returns false for identical duplicate; refuses content conflict. */
    public static synchronized boolean record(
            Context context, String endpoint, String token,
            VeraInboxMessage incoming) throws Exception {
        long now = System.currentTimeMillis() / 1000;
        if (incoming.expiresAt <= now)
            throw new SecurityException("Expired inbound message");
        JSONArray existing = decrypt(context, endpoint, token);
        List<JSONObject> valid = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        for (int i=0; i<existing.length(); i++) {
            JSONObject item = existing.getJSONObject(i);
            VeraInboxMessage old = decode(item, now);
            if (!ids.add(old.messageId))
                throw new SecurityException("Duplicate local message ID");
            if (old.messageId.equals(incoming.messageId)) {
                if (!old.body.equals(incoming.body)
                        || !old.kind.equals(incoming.kind)
                        || old.expiresAt != incoming.expiresAt)
                    throw new SecurityException("Conflicting replayed message");
                return false;
            }
            valid.add(item);
        }
        JSONArray updated = new JSONArray();
        int first = Math.max(0, valid.size() - (MAX_RECORDS - 1));
        for (int i=first; i<valid.size(); i++) updated.put(valid.get(i));
        JSONObject item = new JSONObject()
                .put("message_id", incoming.messageId)
                .put("body", incoming.body)
                .put("kind", incoming.kind)
                .put("expires_at", incoming.expiresAt)
                .put("offer_attempt", incoming.offerAttempt);
        updated.put(item);
        save(context, endpoint, token, updated);
        return true;
    }

    /** Called only on an explicit pairing replacement or UNPAIR. */
    public static synchronized void clear(Context context) {
        if (!prefs(context).edit().clear().commit())
            throw new SecurityException("Could not clear local private inbox");
    }
}
