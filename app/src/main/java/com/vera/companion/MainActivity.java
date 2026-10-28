package com.vera.companion;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** User-initiated, response-only local inference interface. */
public final class MainActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ArrayList<JSONObject> history = new ArrayList<>();
    private EditText endpoint, secret, input;
    private TextView status, conversation;
    private Spinner models;
    private Button send;
    private boolean connected, busy;

    private TextView text(String s, int sp) {
        TextView view = new TextView(this);
        view.setText(s);
        view.setTextSize(sp);
        view.setTextColor(Color.WHITE);
        view.setPadding(8, 10, 8, 10);
        return view;
    }
    private Button addButton(LinearLayout parent, String caption, Runnable action) {
        Button button = new Button(this);
        button.setText(caption);
        button.setOnClickListener(v -> action.run());
        parent.addView(button);
        return button;
    }
    private void state(String detail) {
        status.setText((connected ? "CONNECTED · RESPONSE ONLY" : "UNBOUND · TAILNET ONLY") + "\n" + detail);
        send.setEnabled(connected && !busy);
    }
    private void append(String name, String value) {
        conversation.append("\n" + name + "\n" + value + "\n");
    }

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(18, 22, 34));
        root.setPadding(16, 12, 16, 12);
        setContentView(root);
        root.addView(text("VERA  /  LOCAL INFERENCE", 23));
        status = text("", 13);
        root.addView(status);
        endpoint = new EditText(this);
        endpoint.setTextColor(Color.WHITE);
        endpoint.setHintTextColor(Color.LTGRAY);
        endpoint.setSingleLine(true);
        endpoint.setHint("https://lappy.<tailnet>.ts.net:8443");
        endpoint.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        endpoint.setText(SecureConfig.endpoint(this));
        root.addView(endpoint);
        secret = new EditText(this);
        secret.setTextColor(Color.WHITE);
        secret.setHintTextColor(Color.LTGRAY);
        secret.setHint("Pairing token from Lappy");
        secret.setSingleLine(true);
        secret.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        root.addView(secret);
        LinearLayout controls = new LinearLayout(this);
        root.addView(controls);
        addButton(controls, "SAVE", this::save);
        addButton(controls, "CONNECT", this::connect);
        addButton(controls, "UNPAIR", this::unpair);
        models = new Spinner(this);
        root.addView(models);
        ScrollView scroll = new ScrollView(this);
        conversation = text("Connect through Tailscale to access your local models. No automatic network activity.\n", 16);
        scroll.addView(conversation);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout composer = new LinearLayout(this);
        root.addView(composer);
        input = new EditText(this);
        input.setHint("Message Vera");
        input.setHintTextColor(Color.LTGRAY);
        input.setTextColor(Color.WHITE);
        input.setMaxLines(4);
        composer.addView(input, new LinearLayout.LayoutParams(0, -2, 1));
        send = addButton(composer, "SEND", this::send);
        state(SecureConfig.endpoint(this).isEmpty() ? "No endpoint paired" : "Pairing saved; tap Connect");
    }
    private void save() {
        try {
            SecureConfig.save(this, endpoint.getText().toString(), secret.getText().toString().trim());
            secret.setText("");
            connected = false;
            history.clear();
            state("Saved securely. Tap Connect.");
        } catch (Exception e) { state("Invalid endpoint or token"); }
    }
    private void unpair() {
        SecureConfig.clear(this);
        endpoint.setText("");
        secret.setText("");
        history.clear();
        connected = false;
        state("Pairing erased from this device");
    }
    private void connect() {
        if (busy) return;
        busy = true;
        connected = false;
        state("Checking local gateway...");
        String url = SecureConfig.endpoint(this);
        worker.execute(() -> {
            try {
                List<String> available = GatewayClient.models(url, SecureConfig.token(this));
                if (available.isEmpty()) throw new IllegalStateException("No models");
                runOnUiThread(() -> {
                    models.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, available));
                    busy = false;
                    connected = true;
                    state(available.size() + " models available");
                });
            } catch (Exception e) {
                runOnUiThread(() -> { busy = false; state("Connection refused. Check Tailscale and pairing."); });
            }
        });
    }
    private void send() {
        if (!connected || busy || models.getSelectedItem() == null) return;
        String prompt = input.getText().toString().trim();
        if (prompt.isEmpty() || prompt.length() > 4096) { state("Message must be 1–4096 characters"); return; }
        String selected = models.getSelectedItem().toString();
        JSONArray messages = new JSONArray();
        try {
            for (int i = Math.max(0, history.size() - 10); i < history.size(); i++) messages.put(history.get(i));
            messages.put(new JSONObject().put("role", "user").put("content", prompt));
        } catch (Exception e) { state("Invalid session"); return; }
        String url = SecureConfig.endpoint(this);
        busy = true;
        state("Generating on " + selected + "...");
        worker.execute(() -> {
            try {
                String reply = GatewayClient.chat(url, SecureConfig.token(this), selected, messages);
                runOnUiThread(() -> {
                    try {
                        history.add(new JSONObject().put("role", "user").put("content", prompt));
                        history.add(new JSONObject().put("role", "assistant").put("content", reply));
                    } catch (Exception ignored) { }
                    append("YOU", prompt);
                    append("VERA", reply);
                    input.setText("");
                    busy = false;
                    state("Local model: " + selected);
                });
            } catch (Exception e) {
                runOnUiThread(() -> { busy = false; state("Inference unavailable; no message saved"); });
            }
        });
    }
    @Override public void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
