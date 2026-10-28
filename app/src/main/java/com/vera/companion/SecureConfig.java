package com.vera.companion;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Android Keystore-encrypted credential; backup of preferences is disabled. */
public final class SecureConfig {
    private static final String ALIAS = "vera.tailnet.inference.v1";
    private static final String PREF = "tailnet_inference";
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

    public static void save(Context context, String endpoint, String token) throws Exception {
        String normalized = EndpointPolicy.normalize(endpoint);
        if (token == null || !token.matches("[A-Za-z0-9_-]{32,128}")) {
            throw new IllegalArgumentException("Invalid pairing token");
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putString("url", normalized)
                .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("secret", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .putBoolean("connection_wanted", false).apply();
    }

    public static String endpoint(Context context) {
        return context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getString("url", "");
    }

    public static String token(Context context) throws Exception {
        SharedPreferences prefs = context.getSharedPreferences(PREF, Context.MODE_PRIVATE);
        String enc = prefs.getString("secret", null);
        String iv = prefs.getString("iv", null);
        if (enc == null || iv == null) return null;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128,
                Base64.decode(iv, Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(enc, Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    /** Previous user connection intent, not proof of a live transport. */
    public static boolean wantsConnection(Context context) {
        return context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                .getBoolean("connection_wanted", false);
    }

    public static void setConnectionWanted(Context context, boolean wanted) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
                .putBoolean("connection_wanted", wanted).apply();
    }

    public static void clear(Context context) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().clear().apply();
    }
}
