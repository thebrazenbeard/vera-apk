package com.vera.companion;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        int padding = Math.round(24 * getResources().getDisplayMetrics().density);
        root.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Vera Companion");
        title.setTextSize(28);

        TextView status = new TextView(this);
        status.setText("UNBOUND\nNo runtime route or effect authority is active.");
        status.setTextSize(16);
        status.setGravity(Gravity.CENTER);

        root.addView(title);
        root.addView(status);
        setContentView(root);
    }
}
