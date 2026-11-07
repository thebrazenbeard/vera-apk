package com.vera.companion;

import java.util.concurrent.atomic.AtomicLong;

/** Invalidate old asynchronous work whenever pairing is replaced or erased. */
final class PairingEpoch {
    private final AtomicLong generation = new AtomicLong();

    long capture() {
        return generation.get();
    }

    void invalidate() {
        generation.incrementAndGet();
    }

    boolean isCurrent(long captured) {
        return generation.get() == captured;
    }
}
