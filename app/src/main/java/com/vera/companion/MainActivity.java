package com.vera.companion;

import android.app.Activity;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Foreground-only, user-paired inference client; no effect authority. */
public final class MainActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ArrayList<JSONObject> history = new ArrayList<>();
    private EditText endpoint, secret, input;
    private TextView status;
    private LinearLayout transcript, connectionPanel;
    private Button connectionToggle;
    private Spinner models;
    private Button send, v2NewChat;
    private String v2SessionId = "";
    private boolean usingV2;
    private ScrollView feed;
    private LinearLayout root;
    private ImageView backdrop;
    private boolean connected, busy;
    private boolean foreground;
    private int reconnectAttempts;
    private final Handler retryHandler = new Handler(Looper.getMainLooper());
    private final Runnable reconnect = () -> {
        if (foreground && !connected && !busy && SecureConfig.wantsConnection(this))
            attemptConnection();
    };

    private int dp(int size) {
        return Math.round(size * getResources().getDisplayMetrics().density);
    }

    private TextView text(String value, int sp) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(sp);
        v.setTextColor(Color.WHITE);
        v.setPadding(dp(5), dp(8), dp(5), dp(8));
        return v;
    }

    private Button addButton(LinearLayout parent, String caption, Runnable action) {
        Button b = new Button(this);
        b.setText(caption);
        b.setAllCaps(false);
        b.setTextColor(Color.rgb(255, 232, 232));
        b.setTextSize(13);
        b.setBackground(rounded(Color.rgb(91, 37, 57), Color.rgb(175, 103, 123), 12));
        b.setMinimumHeight(dp(48));
        b.setOnClickListener(v -> action.run());
        parent.addView(b);
        return b;
    }

    private void state(String detail) {
        status.setText((connected ? (usingV2 ? "V2 DEVICE VERIFIED" : "CONNECTED - RESPONSE ONLY")
                : SecureConfig.wantsConnection(this) ? "RECONNECTING - TAILNET" : "UNBOUND - TAILNET ONLY")
                + "\n" + detail);
        send.setEnabled(connected && !busy);
    }

    private GradientDrawable rounded(int fill, int stroke, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(fill);
        shape.setCornerRadius(dp(radius));
        if (stroke != Color.TRANSPARENT) shape.setStroke(dp(1), stroke);
        return shape;
    }

    private void messageBubble(String who, String value) {
        boolean fromUser = who.equals("YOU");
        LinearLayout wrapper = new LinearLayout(this);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(dp(14), dp(12), dp(14), dp(12));
        wrapper.setBackground(rounded(fromUser ? Color.argb(239, 75, 29, 51)
                        : Color.argb(232, 31, 17, 38),
                fromUser ? Color.rgb(200, 118, 137) : Color.rgb(129, 74, 93), 17));
        TextView label = text(who, 11);
        label.setAllCaps(true);
        label.setLetterSpacing(0.13f);
        label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        label.setTextColor(Color.rgb(246, 183, 189));
        wrapper.addView(label);
        TextView words = text(value, 17);
        words.setTextColor(Color.rgb(254, 245, 245));
        words.setLineSpacing(dp(2), 1.06f);
        wrapper.addView(words);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        p.bottomMargin = dp(13);
        if (fromUser) p.leftMargin = dp(30);
        else p.rightMargin = dp(16);
        transcript.addView(wrapper, p);
    }

    private void append(String who, String value) {
        messageBubble(who, value);
        feed.post(() -> feed.fullScroll(View.FOCUS_DOWN));
    }

    private void applySafeInsets() {
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int statusInset;
            int navigationInset;
            int keyboardInset = 0;
            if (Build.VERSION.SDK_INT >= 30) {
                statusInset = insets.getInsets(WindowInsets.Type.statusBars()
                        | WindowInsets.Type.displayCutout()).top;
                navigationInset = insets.getInsets(WindowInsets.Type.navigationBars()).bottom;
                keyboardInset = insets.getInsets(WindowInsets.Type.ime()).bottom;
            } else {
                statusInset = insets.getSystemWindowInsetTop();
                navigationInset = insets.getSystemWindowInsetBottom();
            }
            view.setPadding(dp(16), SafeAreaPadding.top(dp(12), statusInset),
                    dp(16), SafeAreaPadding.bottom(dp(12), navigationInset, keyboardInset));
            return insets;
        });
        root.requestApplyInsets();
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        getWindow().setStatusBarColor(Color.rgb(18, 22, 34));
        getWindow().setNavigationBarColor(Color.BLACK);

        FrameLayout canvas = new FrameLayout(this);
        backdrop = new ImageView(this);
        backdrop.setScaleType(ImageView.ScaleType.CENTER_CROP);
        chooseBackground();
        canvas.addView(backdrop, new FrameLayout.LayoutParams(-1, -1));
        View dimmer = new View(this);
        dimmer.setBackgroundColor(Color.argb(95, 22, 7, 18));
        canvas.addView(dimmer, new FrameLayout.LayoutParams(-1, -1));

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setFocusableInTouchMode(true);
        canvas.addView(root, new FrameLayout.LayoutParams(-1, -1));
        setContentView(canvas);
        applySafeInsets();

        feed = new ScrollView(this);
        feed.setFillViewport(false);
        root.addView(feed, new LinearLayout.LayoutParams(-1, 0, 1f));
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        feed.addView(content);
        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setGravity(Gravity.CENTER);
        brand.setPadding(dp(8), dp(16), dp(8), dp(13));
        brand.setBackground(rounded(Color.argb(184, 39, 12, 28), Color.rgb(140, 74, 93), 18));
        TextView masthead = text("V E R A", 37);
        masthead.setTypeface(Typeface.create("serif", Typeface.NORMAL));
        masthead.setTextColor(Color.rgb(255, 219, 224));
        masthead.setGravity(Gravity.CENTER);
        brand.addView(masthead);
        TextView subtitle = text("PRIVATE  /  LOCAL INFERENCE", 11);
        subtitle.setLetterSpacing(0.2f);
        subtitle.setTextColor(Color.rgb(241, 166, 180));
        subtitle.setGravity(Gravity.CENTER);
        brand.addView(subtitle);
        LinearLayout.LayoutParams brandSize = new LinearLayout.LayoutParams(-1, -2);
        brandSize.bottomMargin = dp(12);
        content.addView(brand, brandSize);
        status = text("", 13);
        status.setLineSpacing(dp(2), 1.08f);
        status.setBackground(rounded(Color.argb(226, 28, 14, 30), Color.rgb(115, 74, 88), 14));
        status.setPadding(dp(15), dp(12), dp(15), dp(12));
        LinearLayout.LayoutParams statusSize = new LinearLayout.LayoutParams(-1, -2);
        statusSize.bottomMargin = dp(10);
        content.addView(status, statusSize);
        connectionToggle = addButton(content, "CONNECTION SETTINGS  ▾", () -> {
            boolean show = connectionPanel.getVisibility() != View.VISIBLE;
            connectionPanel.setVisibility(show ? View.VISIBLE : View.GONE);
            connectionToggle.setText(show ? "CONNECTION SETTINGS  ▴" : "CONNECTION SETTINGS  ▾");
        });
        v2NewChat = addButton(content, "NEW SECURE CHAT", this::newSecureChat);
        v2NewChat.setVisibility(View.GONE);
        connectionPanel = new LinearLayout(this);
        connectionPanel.setOrientation(LinearLayout.VERTICAL);
        connectionPanel.setPadding(dp(10), dp(8), dp(10), dp(8));
        connectionPanel.setBackground(rounded(Color.argb(235, 35, 18, 36),
                Color.rgb(127, 79, 94), 14));
        content.addView(connectionPanel);
        connectionPanel.setVisibility(SecureConfig.endpoint(this).isEmpty()
                ? View.VISIBLE : View.GONE);
        endpoint = new EditText(this);
        endpoint.setTextColor(Color.WHITE);
        endpoint.setHintTextColor(Color.LTGRAY);
        endpoint.setSingleLine(true);
        endpoint.setHint("https://lappy.<tailnet>.ts.net:8443 (legacy) or :8444 (V2)");
        endpoint.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        endpoint.setText(SecureConfig.endpoint(this));
        connectionPanel.addView(endpoint);
        secret = new EditText(this);
        secret.setTextColor(Color.WHITE);
        secret.setHintTextColor(Color.LTGRAY);
        secret.setHint("Pairing token from Lappy");
        secret.setSingleLine(true);
        secret.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        connectionPanel.addView(secret);
        LinearLayout controls = new LinearLayout(this);
        connectionPanel.addView(controls);
        addButton(controls, "SAVE", this::save);
        addButton(controls, "CONNECT", this::connect);
        addButton(controls, "UNPAIR", this::unpair);
        TextView modelLabel = text("INFERENCE MODEL  /  SELECT", 11);
        modelLabel.setLetterSpacing(0.11f);
        modelLabel.setTextColor(Color.rgb(255, 185, 202));
        content.addView(modelLabel);
        models = new Spinner(this);
        models.setPadding(dp(13), dp(10), dp(13), dp(10));
        models.setBackground(rounded(Color.argb(236, 42, 22, 39),
                Color.rgb(148, 83, 108), 13));
        LinearLayout.LayoutParams modelSize = new LinearLayout.LayoutParams(-1, -2);
        modelSize.bottomMargin = dp(12);
        content.addView(models, modelSize);
        transcript = new LinearLayout(this);
        transcript.setOrientation(LinearLayout.VERTICAL);
        transcript.setPadding(dp(2), dp(8), dp(2), dp(10));
        content.addView(transcript);
        TextView intro = text("Private inference  •  Response only\n"
                + "Your home models respond through Tailscale.", 13);
        intro.setTextColor(Color.rgb(249, 211, 220));
        intro.setGravity(Gravity.CENTER);
        intro.setBackground(rounded(Color.argb(215, 41, 17, 34),
                Color.rgb(121, 66, 85), 13));
        LinearLayout.LayoutParams introSize = new LinearLayout.LayoutParams(-1, -2);
        introSize.bottomMargin = dp(17);
        transcript.addView(intro, introSize);

        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        composer.setPadding(dp(4), dp(7), dp(4), dp(4));
        composer.setBackground(rounded(Color.argb(246, 31, 15, 30), Color.rgb(145, 76, 100), 17));
        root.addView(composer, new LinearLayout.LayoutParams(-1, -2));
        input = new EditText(this);
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(Color.LTGRAY);
        input.setHint("Message Vera...");
        input.setTextSize(17);
        input.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(4);
        input.setMinHeight(dp(56));
        input.setGravity(Gravity.TOP);
        input.setPadding(dp(12), dp(9), dp(12), dp(9));
        input.setImeOptions(EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(55, 31, 49));
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), Color.rgb(197, 117, 146));
        input.setBackground(background);
        LinearLayout.LayoutParams messageSize = new LinearLayout.LayoutParams(0, -2, 1f);
        messageSize.rightMargin = dp(8);
        composer.addView(input, messageSize);
        send = addButton(composer, "SEND", this::send);
        send.setMinimumWidth(dp(74));
        send.setTextColor(Color.WHITE);
        send.setBackground(rounded(Color.rgb(159, 59, 90), Color.rgb(222, 136, 158), 13));
        root.requestFocus();
        state(SecureConfig.endpoint(this).isEmpty() ? "No endpoint paired" : "Tap CONNECT");
    }

    private void chooseBackground() {
        int orientation = getResources().getConfiguration().orientation;
        backdrop.setImageResource(orientation == Configuration.ORIENTATION_LANDSCAPE
                ? R.drawable.vera_phone_landscape : R.drawable.vera_phone_portrait);
    }

    @Override public void onConfigurationChanged(Configuration updated) {
        super.onConfigurationChanged(updated);
        chooseBackground();
        root.requestApplyInsets();
    }

    private void save() {
        try {
            SecureConfig.save(this, endpoint.getText().toString(), secret.getText().toString().trim());
            secret.setText("");
            connected = false;
            history.clear();
            usingV2 = false;
            v2SessionId = "";
            v2NewChat.setVisibility(View.GONE);
            connectionPanel.setVisibility(View.GONE);
            connectionToggle.setText("CONNECTION SETTINGS  ▾");
            state("Saved securely. Tap CONNECT.");
        } catch (Exception e) { state("Invalid endpoint or token"); }
    }

    private void unpair() {
        SecureConfig.clear(this);
        endpoint.setText("");
        secret.setText("");
        history.clear();
        usingV2 = false;
        v2SessionId = "";
        v2NewChat.setVisibility(View.GONE);
        connected = false;
        retryHandler.removeCallbacks(reconnect);
        state("Pairing erased from this device");
    }

    private void connect() {
        if (busy) return;
        SecureConfig.setConnectionWanted(this, true);
        reconnectAttempts = 0;
        retryHandler.removeCallbacks(reconnect);
        attemptConnection();
    }

    private void scheduleReconnect() {
        if (!foreground || !SecureConfig.wantsConnection(this)) return;
        retryHandler.removeCallbacks(reconnect);
        retryHandler.postDelayed(reconnect,
                ConnectionPolicy.reconnectDelayMs(reconnectAttempts++));
    }

    private void attemptConnection() {
        if (busy || !SecureConfig.wantsConnection(this)) return;
        busy = true;
        connected = false;
        state("Checking local gateway...");
        String url = SecureConfig.endpoint(this);
        worker.execute(() -> {
            try {
                boolean v2 = V2GatewayClient.enabled(url);
                String token = SecureConfig.token(this);
                List<String> available = v2 ? V2GatewayClient.models(url, token)
                        : GatewayClient.models(url, token);
                String restoredSession = "";
                JSONArray restoredHistory = null;
                if (v2) {
                    List<String> ids = V2GatewayClient.sessions(url, token);
                    String preferred = SecureConfig.v2SessionId(this);
                    restoredSession = ids.contains(preferred) ? preferred
                            : (ids.isEmpty() ? V2GatewayClient.createSession(url,token) : ids.get(0));
                    restoredHistory = V2GatewayClient.history(url,token,restoredSession);
                }
                final String sessionReady = restoredSession;
                final JSONArray recovered = restoredHistory;
                if (available.isEmpty()) throw new IllegalStateException("No models");
                runOnUiThread(() -> {
                    ArrayAdapter<String> adapter = new ArrayAdapter<String>(this,
                            android.R.layout.simple_spinner_item, available) {
                        @Override public View getView(int position, View convertView, ViewGroup parent) {
                            TextView v = (TextView) super.getView(position, convertView, parent);
                            v.setTextColor(Color.WHITE);
                            v.setPadding(dp(5), dp(10), dp(5), dp(10));
                            return v;
                        }
                    };
                    adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    String previous = models.getSelectedItem() == null ? ""
                            : models.getSelectedItem().toString();
                    models.setAdapter(adapter);
                    int matching = ModelPreference.choose(available, previous);
                    if (matching >= 0) models.setSelection(matching);
                    usingV2 = v2;
                    if (v2) {
                        v2SessionId = sessionReady;
                        SecureConfig.setV2SessionId(this, sessionReady);
                        renderV2History(recovered);
                    }
                    v2NewChat.setVisibility(v2 ? View.VISIBLE : View.GONE);
                    busy = false;
                    connected = true;
                    reconnectAttempts = 0;
                    retryHandler.removeCallbacks(reconnect);
                    state(available.size() + (v2 ? " secured V2 models; history restored"
                            : " legacy models available"));
                });
            } catch (Exception e) {
                boolean unauthorized = ConnectionPolicy.requiresPairing(e.getMessage());
                runOnUiThread(() -> {
                    busy = false;
                    if (unauthorized) SecureConfig.setConnectionWanted(this, false);
                    state(unauthorized ? "Pairing rejected. Check your token."
                            : "Gateway unavailable; retrying while app is open.");
                    if (!unauthorized) scheduleReconnect();
                });
            }
        });
    }

    private void renderV2History(JSONArray turns) {
        transcript.removeAllViews();
        history.clear();
        for (int i=0; i<turns.length(); i++) {
            try {
                JSONObject turn = turns.getJSONObject(i);
                append("YOU", turn.getString("user"));
                append("VERA - " + turn.getString("model"), turn.getString("assistant"));
            } catch (Exception e) {
                transcript.removeAllViews();
                append("SYSTEM", "Private history could not be reconstructed");
                throw new IllegalStateException("Unusable V2 history",e);
            }
        }
        if (turns.length()==0) append("VERA", "New encrypted conversation, authorized by this device.");
    }

    private void newSecureChat() {
        if (!connected || busy || !usingV2) return;
        busy = true;
        state("Creating owner-scoped private conversation...");
        String url = SecureConfig.endpoint(this);
        worker.execute(() -> {
            try {
                String id=V2GatewayClient.createSession(url,SecureConfig.token(this));
                runOnUiThread(() -> {
                    v2SessionId=id;
                    SecureConfig.setV2SessionId(this,id);
                    transcript.removeAllViews();
                    history.clear();
                    append("VERA","New private conversation opened");
                    busy=false;
                    state("New V2 conversation ready");
                });
            } catch (Exception e) {
                runOnUiThread(() -> { busy=false; state("V2 session creation refused"); });
            }
        });
    }

    private void send() {
        if (!connected || busy || models.getSelectedItem() == null) return;
        String prompt = input.getText().toString().trim();
        if (prompt.isEmpty() || prompt.length() > 4096) {
            state("Message must be 1-4096 characters");
            return;
        }
        String selected = models.getSelectedItem().toString();
        if (usingV2 && (v2SessionId == null || v2SessionId.isEmpty())) {
            state("V2 session must be recovered before sending");
            return;
        }
        JSONArray messages = new JSONArray();
        try {
            for (int i = Math.max(0, history.size() - 10); i < history.size(); i++)
                messages.put(history.get(i));
            messages.put(new JSONObject().put("role", "user").put("content", prompt));
        } catch (Exception e) { state("Invalid session"); return; }
        String url = SecureConfig.endpoint(this);
        busy = true;
        append("YOU", prompt);
        input.setText("");
        state("Message queued - Vera is generating on " + selected + "...");
        final String requestId = java.util.UUID.randomUUID().toString().replace("-", "");
        worker.execute(() -> {
            try {
                String token = SecureConfig.token(this);
                String reply = usingV2
                        ? V2GatewayClient.chat(url,token,selected,v2SessionId,requestId,prompt)
                        : GatewayClient.chat(url,token,selected,messages,
                            SecureConfig.sessionId(this),requestId);
                runOnUiThread(() -> {
                    try {
                        history.add(new JSONObject().put("role", "user").put("content", prompt));
                        history.add(new JSONObject().put("role", "assistant").put("content", reply));
                    } catch (Exception ignored) { }
                    append("VERA  •  " + selected, reply);
                    busy = false;
                    state("Serving model: " + selected);
                });
            } catch (Exception e) {
                boolean authenticationLost = ConnectionPolicy.requiresPairing(e.getMessage());
                runOnUiThread(() -> {
                    busy = false;
                    if (authenticationLost) {
                        connected = false;
                        SecureConfig.setConnectionWanted(this, false);
                        retryHandler.removeCallbacks(reconnect);
                    }
                    if (input.getText().toString().isEmpty()) input.setText(prompt);
                    append("SYSTEM", usingV2
                            ? "Delivery uncertain. Draft restored; check encrypted history before retry."
                            : "Message not delivered. Your draft is restored.");
                    state(authenticationLost ? "Pairing rejected; reconnect to retry."
                            : usingV2 ? "V2 response uncertain; reconnect to inspect saved history."
                            : "Message not delivered; retry when ready.");
                });
            }
        });
    }

    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        if (SecureConfig.wantsConnection(this) && !busy) attemptConnection();
    }

    @Override protected void onPause() {
        foreground = false;
        retryHandler.removeCallbacks(reconnect);
        super.onPause();
    }

    @Override public void onDestroy() {
        retryHandler.removeCallbacks(reconnect);
        worker.shutdownNow();
        super.onDestroy();
    }
}
