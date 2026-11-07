package com.vera.companion;

/** Serializes speaker startup against focus-loss and lifecycle close. */
final class VoicePlaybackGate {
    private boolean closed;

    synchronized void runWhileOpen(Runnable start) {
        if (closed) throw new IllegalStateException("Playback already closed");
        start.run();
    }

    synchronized boolean closeOnce() {
        if (closed) return false;
        closed = true;
        return true;
    }
}
