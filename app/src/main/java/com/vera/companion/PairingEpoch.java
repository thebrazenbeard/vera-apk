package com.vera.companion;

import java.util.concurrent.atomic.AtomicLong;

/** Invalidate old asynchronous work whenever pairing is replaced or erased. */
final class PairingEpoch {
    private final AtomicLong generation = new AtomicLong();

    long capture() {
        return generation.get();
    }

    // Shares a monitor with network dispatch; UNPAIR linearizes at this increment.
    synchronized void invalidate() {
        generation.incrementAndGet();
    }

    @FunctionalInterface interface SendOperation {
        void run() throws Exception;
    }

    /** Gate only the transport's request write, never its response wait.
     * If a write has begun, invalidation waits for that write to finish. A request
     * already sent cannot be recalled from the server or network buffers.
     */
    synchronized void sendIfCurrent(long captured, SendOperation send) throws Exception {
        if (!isCurrent(captured))
            throw new java.util.concurrent.CancellationException("Pairing revoked before dispatch");
        send.run();
    }

    boolean isCurrent(long captured) {
        return generation.get() == captured;
    }
}
