package com.vera.companion;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Android Keystore-encrypted credential; backup of preferences is disabled. */
public final class SecureConfig {
    private static final String ALIAS = "vera.tailnet.inference.v1";
    private static final String PREF = "tailnet_inference";
    // In-process barrier survives failed SharedPreferences/Keystore writes, not a reboot.
    private static volatile boolean revokedInProcess;
    private SecureConfig() {}

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        SecretKey found = (SecretKey) store.getKey(ALIAS, null);
        if (found != null) return found;
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return generator.generateKey();
    }

    private static SecretKey existingKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        SecretKey existing = (SecretKey) store.getKey(ALIAS, null);
        if (existing == null) throw new SecurityException("Pairing key revoked or unavailable");
        return existing;
    }

    private static void revokeBearerKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS);
        if (store.containsAlias(ALIAS))
            throw new SecurityException("Pairing key erasure was not verified");
    }

    public static void save(Context context, String endpoint, String token) throws Exception {
        String normalized = EndpointPolicy.normalize(endpoint);
        if (token == null || !token.matches("[A-Za-z0-9_-]{32,128}")) {
            throw new IllegalArgumentException("Invalid pairing token");
        }
        // A replacement begins a fresh authority epoch even if encryption fails.
        revokedInProcess = true;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        // Pairing replacement must be durably persisted before reporting success.
        // An asynchronous apply() could resurrect the previous bearer after a crash.
        boolean saved = context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putString("url", normalized)
                .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("secret", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .remove("v2_session_id")
                .putBoolean("connection_wanted", false).commit();
        if (!saved) {
            revokedInProcess = true;
            try { revokeBearerKey(); } catch (Exception ignored) { /* two-store failure */ }
            throw new SecurityException("Pairing persistence failed; bearer invalidation attempted");
        }
        revokedInProcess = false;
    }

    public static String endpoint(Context context) {
        return context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getString("url", "");
    }

    public static String token(Context context) throws Exception {
        if (revokedInProcess) throw new SecurityException("Pairing revoked in this process");
        SharedPreferences prefs = context.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        String enc = prefs.getString("secret", null);
        String iv = prefs.getString("iv", null);
        if (enc == null || iv == null) return null;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, existingKey(), new GCMParameterSpec(128,
                Base64.decode(iv, Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(enc, Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    /** Previous user connection intent, not proof of a live transport. */
    public static boolean wantsConnection(Context context) {
        return !revokedInProcess && context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .getBoolean("connection_wanted", false);
    }

    public static void setConnectionWanted(Context context, boolean wanted) {
        if (wanted && revokedInProcess)
            throw new SecurityException("Cannot reconnect after an incomplete unpair");
        if (!context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putBoolean("connection_wanted", wanted).commit())
            throw new SecurityException("Connection preference not persisted");
    }

    /** UI rejoin hint only; the V2 server authorizes every retrieval by device bearer. */
    public static String v2SessionId(Context context) {
        return context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .getString("v2_session_id", "");
    }

    public static void setV2SessionId(Context context, String session) {
        if (session == null || !session.matches("[A-Za-z0-9_-]{16,128}"))
            throw new IllegalArgumentException("Invalid server session ID");
        if (!context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putString("v2_session_id", session).commit())
            throw new SecurityException("V2 session hint persistence failed");
    }

    /** Stable pseudonymous device-session identifier, regenerated on UNPAIR. */
    public static String sessionId(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        String existing = prefs.getString("chat_session_id", "");
        if (existing != null && existing.matches("[a-f0-9]{32}")) return existing;
        String created = UUID.randomUUID().toString().replace("-", "");
        prefs.edit().putString("chat_session_id", created).commit();
        return created;
    }

    public static void clear(Context context) {
        revokedInProcess = true;
        // Independent erasure routes: even if preferences cannot commit, deleting
        // this sole bearer key makes saved ciphertext unusable after a restart.
        Exception keyFailure = null;
        try { revokeBearerKey(); } catch (Exception e) { keyFailure = e; }
        boolean preferencesCleared = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .edit().clear().commit();
        if (!preferencesCleared || keyFailure != null)
            throw new SecurityException("Pairing erasure incomplete; reboot safety unverified");
    }
}
