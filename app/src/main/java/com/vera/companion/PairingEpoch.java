package com.vera.companion;

import java.util.concurrent.atomic.AtomicLong;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

/** Invalidate old asynchronous work whenever pairing is replaced or erased. */
final class PairingEpoch {
    private final AtomicLong generation = new AtomicLong();

    long capture() {
        return generation.get();
    }

    private final Set<SendPermit> active = new HashSet<>();

    /** Cancellation intent is immediate; an already-issued HTTP request is not retractable. */
    void invalidate() {
        ArrayList<SendPermit> outstanding;
        synchronized (this) {
            generation.incrementAndGet();
            outstanding = new ArrayList<>(active);
            for (SendPermit permit : outstanding) permit.revoked = true;
            active.clear();
        }
        // A disconnect may block in the network stack; never perform it on the UI thread.
        for (SendPermit permit : outstanding) permit.abortAsync();
    }

    static final class SendPermit {
        private final Runnable abort;
        private volatile boolean revoked;
        SendPermit(Runnable abort) { this.abort = abort; }
        void requireActive() {
            if (revoked)
                throw new java.util.concurrent.CancellationException("Pairing revoked before write");
        }
        void abortAsync() {
            if (abort == null) return;
            Thread thread = new Thread(() -> {
                try { abort.run(); } catch (RuntimeException ignored) { }
            }, "vera-pairing-abort");
            thread.setDaemon(true);
            thread.start();
        }
    }

    @FunctionalInterface interface SendOperation {
        void run(SendPermit permit) throws Exception;
    }

    /** Admission and revocation are atomic, but network delivery is not.
     * Unpair never holds a monitor during DNS, TLS, upload, or response handling.
     */
    void sendIfCurrent(long captured, Runnable abort, SendOperation send) throws Exception {
        SendPermit permit;
        synchronized (this) {
            if (!isCurrent(captured))
                throw new java.util.concurrent.CancellationException("Pairing revoked before dispatch");
            permit = new SendPermit(abort);
            active.add(permit);
        }
        try {
            permit.requireActive();
            send.run(permit);
        } finally {
            synchronized (this) { active.remove(permit); }
        }
    }

    boolean isCurrent(long captured) {
        return generation.get() == captured;
    }
}
