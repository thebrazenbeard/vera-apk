package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Pairing replacement invalidates every in-flight callback, even for the same URL. */
public final class PairingEpochTest {
    @Test public void saveOrUnpairRevokesPriorResults() {
        PairingEpoch epoch = new PairingEpoch();
        long oldPairing = epoch.capture();
        assertTrue(epoch.isCurrent(oldPairing));
        epoch.invalidate(); // SAVE or UNPAIR
        assertFalse("old connection result must be discarded", epoch.isCurrent(oldPairing));
        long replacement = epoch.capture();
        assertTrue(epoch.isCurrent(replacement));
        epoch.invalidate(); // second pairing replacement
        assertFalse(epoch.isCurrent(replacement));
    }

    @Test public void concurrentInvalidationIsVisibleToWorker() throws Exception {
        PairingEpoch epoch = new PairingEpoch();
        long captured = epoch.capture();
        Thread changer = new Thread(epoch::invalidate);
        changer.start();
        changer.join();
        assertFalse("old response must not render after UNPAIR", epoch.isCurrent(captured));
    }

    @Test public void unpairBetweenWorkerCheckAndTransportWriteRevokesSend()
            throws Exception {
        PairingEpoch epoch = new PairingEpoch();
        long captured = epoch.capture();
        CountDownLatch checked = new CountDownLatch(1);
        CountDownLatch resume = new CountDownLatch(1);
        AtomicInteger sent = new AtomicInteger();
        AtomicInteger rejected = new AtomicInteger();
        Thread worker = new Thread(() -> {
            if (!epoch.isCurrent(captured)) return;
            checked.countDown();
            try {
                if (!resume.await(5, TimeUnit.SECONDS)) return;
                epoch.sendIfCurrent(captured, () -> { },
                        permit -> { permit.requireActive(); sent.incrementAndGet(); });
            } catch (java.util.concurrent.CancellationException revoked) {
                rejected.incrementAndGet();
            } catch (Exception e) { throw new AssertionError(e); }
        });
        worker.start();
        assertTrue(checked.await(5, TimeUnit.SECONDS));
        epoch.invalidate(); // UNPAIR before the HTTPS write gate
        resume.countDown();
        worker.join(5000);
        assertFalse(worker.isAlive());
        assertEquals(0, sent.get());
        assertEquals(1, rejected.get());
    }

    @Test public void unpairReturnsWhileTransportIsBlocked() throws Exception {
        PairingEpoch epoch = new PairingEpoch();
        long captured = epoch.capture();
        CountDownLatch sending = new CountDownLatch(1);
        CountDownLatch finishSend = new CountDownLatch(1);
        CountDownLatch abortCalled = new CountDownLatch(1);
        CountDownLatch revokeDone = new CountDownLatch(1);
        AtomicInteger rejected = new AtomicInteger();
        Thread worker = new Thread(() -> {
            try {
                epoch.sendIfCurrent(captured, abortCalled::countDown, permit -> {
                    sending.countDown();
                    if (!finishSend.await(5, TimeUnit.SECONDS))
                        throw new IllegalStateException("test send timeout");
                    permit.requireActive();
                });
            } catch (java.util.concurrent.CancellationException expected) {
                rejected.incrementAndGet();
            } catch (Exception e) { throw new AssertionError(e); }
        });
        worker.start();
        assertTrue(sending.await(5, TimeUnit.SECONDS));
        Thread revoker = new Thread(() -> {
            epoch.invalidate();
            revokeDone.countDown();
        });
        revoker.start();
        assertTrue("UNPAIR blocked on transport I/O",
                revokeDone.await(1, TimeUnit.SECONDS));
        assertTrue("Disconnect was not scheduled", abortCalled.await(1, TimeUnit.SECONDS));
        assertTrue("Worker did not remain blocked for the liveness probe", worker.isAlive());
        finishSend.countDown();
        worker.join(5000);
        revoker.join(5000);
        assertFalse(worker.isAlive());
        assertFalse(revoker.isAlive());
        assertFalse(epoch.isCurrent(captured));
        assertEquals(1, rejected.get());
    }

    @Test public void delayedNetworkCompletionIsRejectedAfterPairingReplacement()
            throws Exception {
        PairingEpoch epoch = new PairingEpoch();
        long oldGeneration = epoch.capture();
        CountDownLatch requestStarted = new CountDownLatch(1);
        CountDownLatch allowCompletion = new CountDownLatch(1);
        AtomicInteger renderedCallbacks = new AtomicInteger();
        Thread worker = new Thread(() -> {
            requestStarted.countDown();
            try {
                if (!allowCompletion.await(5, TimeUnit.SECONDS)) return;
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                return;
            }
            if (epoch.isCurrent(oldGeneration)) renderedCallbacks.incrementAndGet();
        });
        worker.start();
        assertTrue("network request failed to start", requestStarted.await(5, TimeUnit.SECONDS));
        epoch.invalidate(); // SAVE/UNPAIR before delayed network result
        allowCompletion.countDown();
        worker.join(5000);
        assertFalse("worker failed to finish", worker.isAlive());
        assertEquals("stale pairing callback was accepted", 0, renderedCallbacks.get());

        long freshGeneration = epoch.capture();
        if (epoch.isCurrent(freshGeneration)) renderedCallbacks.incrementAndGet();
        assertEquals("current pairing callback was incorrectly suppressed",
                1, renderedCallbacks.get());
    }
}
