package com.vera.companion;

import java.util.Objects;

/**
 * JVM-testable playback ownership, not a gesture authenticator.
 * A caller must verify its UI action is visible before passing true.
 * No constructor, lifecycle transition, or hidden tap can start playback.
 */
final class VoiceTapSession implements AutoCloseable {
    interface PlaybackHandle { void close(); }
    interface Launcher { PlaybackHandle start(); }

    private final Launcher launcher;
    private PlaybackHandle active;
    private boolean closed;

    VoiceTapSession(Launcher launcher) {
        this.launcher = Objects.requireNonNull(launcher, "launcher");
    }

    /** All launch/close transitions serialize; a closing lifecycle wins permanently. */
    synchronized boolean onVisibleTap(boolean visible) {
        if (!visible || closed) return false;
        closeActive();
        // Closing the previous handle can synchronously reenter close(). A
        // lifecycle close wins even when it happens during this tap's callback.
        if (closed) return false;
        PlaybackHandle started = Objects.requireNonNull(
                launcher.start(), "Playback launcher returned null");
        // Likewise a launcher can synchronously trigger teardown before it returns.
        if (closed) {
            started.close();
            return false;
        }
        active = started;
        return true;
    }

    @Override public synchronized void close() {
        if (closed) return;
        closed = true;
        closeActive();
    }

    private void closeActive() {
        PlaybackHandle prior = active;
        active = null;
        if (prior != null) prior.close();
    }
}
