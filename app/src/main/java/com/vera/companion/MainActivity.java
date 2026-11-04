package com.vera.companion;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        int padding = Math.round(24 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Vera Companion");
        title.setTextSize(28);
        TextView explanation = new TextView(this);
        explanation.setText("Choose a possible Lappy/VN inference host. This screen validates syntax only; it does not connect.");
        Spinner host = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item,
                new String[]{"Lappy", "VN1", "VN2"});
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        host.setAdapter(adapter);
        EditText origin = new EditText(this);
        origin.setSingleLine(true);
        origin.setHint("https://host.tailnet.ts.net:port");
        origin.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        Button check = new Button(this);
        check.setText("Validate candidate");
        TextView status = new TextView(this);
        status.setText("UNBOUND\nNo runtime route or effect authority is active.");
        status.setTextSize(16);
        check.setOnClickListener(view -> {
            try {
                InferenceEndpointPolicy.Candidate candidate = InferenceEndpointPolicy.validate(
                        host.getSelectedItem().toString(), origin.getText().toString());
                status.setText("VALID ORIGIN CANDIDATE\n" + candidate.hostLabel + ": " +
                        candidate.origin + "\nNOT CONNECTED - no pairing, API contract, or permission established.");
            } catch (IllegalArgumentException e) {
                status.setText("UNBOUND\n" + e.getMessage());
            }
        });
        root.addView(title);
        root.addView(explanation);
        root.addView(host);
        root.addView(origin);
        root.addView(check);
        root.addView(status);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
    }
}
