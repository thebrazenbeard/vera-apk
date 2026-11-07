package com.vera.companion;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.Bundle;
import android.os.Looper;
import android.view.View;
import java.util.Objects;

/**
 * Opt-in audio-only adapter for a DEDICATED, visible Play Voice button.
 * It does not create a button, attach to existing chat UI, or auto-play responses.
 * The UI owner must call bind() from the foreground Activity on the main thread.
 */
public final class VoiceTapBinding implements AutoCloseable {
    private final Activity activity;
    private final View playControl;
    private final VoiceTapSession session;
    private final VoiceTapLease lease;
    private final Application.ActivityLifecycleCallbacks lifecycle;
    private final View.OnAttachStateChangeListener attachment;
    private boolean closed;

    private VoiceTapBinding(Activity activity, View playControl, byte[] validatedWave,
                            VoiceTapLease lease) {
        this.activity = activity;
        this.playControl = playControl;
        this.lease = lease;
        this.session = new VoiceTapSession(
                () -> VoiceWavePlayer.playFromUserTap(activity, validatedWave)::close);
        this.lifecycle = new Application.ActivityLifecycleCallbacks() {
            @Override public void onActivityCreated(Activity candidate, Bundle state) { }
            @Override public void onActivityStarted(Activity candidate) { }
            @Override public void onActivityResumed(Activity candidate) { }
            @Override public void onActivityPaused(Activity candidate) { }
            @Override public void onActivitySaveInstanceState(Activity candidate, Bundle state) { }
            @Override public void onActivityStopped(Activity candidate) {
                if (candidate == activity) close();
            }
            @Override public void onActivityDestroyed(Activity candidate) {
                if (candidate == activity) close();
            }
        };
        this.attachment = new View.OnAttachStateChangeListener() {
            @Override public void onViewAttachedToWindow(View view) { }
            @Override public void onViewDetachedFromWindow(View view) { close(); }
        };
    }

    /**
     * The supplied button must be exclusively owned by this binding: it replaces its
     * click listener. The immutable snapshot is capped and parsed before registration.
     * Instantiating this binding does not start playback.
     */
    public static VoiceTapBinding bind(Activity activity, View playControl, byte[] wave) {
        requireMainThread();
        Objects.requireNonNull(activity, "activity");
        Objects.requireNonNull(playControl, "playControl");
        Objects.requireNonNull(wave, "wave");
        if (activity.isFinishing() || activity.isDestroyed()) {
            throw new IllegalStateException("Cannot bind a finishing Activity");
        }
        if (!belongsToActivity(playControl.getContext(), activity)) {
            throw new IllegalArgumentException("Play control is not owned by this Activity");
        }
        if (wave.length > VoiceWav16.MAX_WAV_BYTES) {
            throw new IllegalArgumentException("WAV exceeds accepted byte bound");
        }
        // Clone first: neither the user tap nor another thread can mutate the payload.
        byte[] snapshot = wave.clone();
        VoiceWav16.parse(snapshot);
        Object existing = playControl.getTag(R.id.vera_voice_tap_binding_lease);
        if (existing != null && !(existing instanceof VoiceTapLease)) {
            throw new IllegalStateException("Voice tap binding tag collision");
        }
        VoiceTapLease lease = existing == null ? new VoiceTapLease() : (VoiceTapLease) existing;
        VoiceTapBinding binding = new VoiceTapBinding(activity, playControl, snapshot, lease);
        if (!lease.claim(binding)) {
            throw new IllegalStateException("Close the previous voice binding before rebinding");
        }
        if (existing == null) playControl.setTag(R.id.vera_voice_tap_binding_lease, lease);
        activity.getApplication().registerActivityLifecycleCallbacks(binding.lifecycle);
        playControl.addOnAttachStateChangeListener(binding.attachment);
        playControl.setOnClickListener(view -> {
            if (!binding.closed && !activity.isFinishing() && !activity.isDestroyed()) {
                // OnClick alone cannot prove human origin (performClick can synthesize it).
                // Require the dedicated control to be actually on-screen and focused.
                binding.session.onVisibleTap(view.isAttachedToWindow()
                        && view.isShown() && view.hasWindowFocus() && view.isEnabled());
            }
        });
        return binding;
    }

    @Override public void close() {
        requireMainThread();
        if (closed) return;
        closed = true;
        // Only the current lease owner may clear this control's listener.
        if (lease.release(this)) playControl.setOnClickListener(null);
        playControl.removeOnAttachStateChangeListener(attachment);
        activity.getApplication().unregisterActivityLifecycleCallbacks(lifecycle);
        session.close();
    }

    private static void requireMainThread() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            throw new IllegalStateException("Voice tap binding must run on Android main thread");
        }
    }

    private static boolean belongsToActivity(Context context, Activity owner) {
        // ContextThemeWrapper may surround the real Activity; reject a control
        // originating from a different Activity or the Application context.
        for (int depth = 0; context != null && depth < 16; depth++) {
            if (context == owner) return true;
            if (!(context instanceof ContextWrapper)) return false;
            Context next = ((ContextWrapper) context).getBaseContext();
            if (next == context) return false;
            context = next;
        }
        return false;
    }
}
