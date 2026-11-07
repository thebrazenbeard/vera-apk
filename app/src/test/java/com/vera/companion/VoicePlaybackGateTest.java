package com.vera.companion;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.Test;

public final class VoicePlaybackGateTest {
    @Test public void focusLossBeforeStartupPermanentlyRejectsPlayback() {
        VoicePlaybackGate gate = new VoicePlaybackGate();
        assertTrue(gate.closeOnce());
        assertFalse(gate.closeOnce());
        try {
            gate.runWhileOpen(() -> fail("Playback ran after focus loss"));
            fail("Playback gate reopened after close");
        } catch (IllegalStateException expected) { }
    }

    @Test public void focusLossCannotInterleaveStartupResourceAssignment() throws Exception {
        VoicePlaybackGate gate = new VoicePlaybackGate();
        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch finishStartup = new CountDownLatch(1);
        CountDownLatch closeAttempted = new CountDownLatch(1);
        CountDownLatch closeFinished = new CountDownLatch(1);
        AtomicBoolean playbackLaunched = new AtomicBoolean();
        Thread startup = new Thread(() -> gate.runWhileOpen(() -> {
            started.countDown();
            await(finishStartup);
            playbackLaunched.set(true);
        }));
        Thread loss = new Thread(() -> {
            closeAttempted.countDown();
            gate.closeOnce();
            closeFinished.countDown();
        });
        startup.start();
        assertTrue(started.await(2, TimeUnit.SECONDS));
        loss.start();
        assertTrue(closeAttempted.await(2, TimeUnit.SECONDS));
        try {
            assertFalse("Focus close interleaved guarded startup",
                    closeFinished.await(100, TimeUnit.MILLISECONDS));
        } finally {
            finishStartup.countDown();
            startup.join(2_000);
            loss.join(2_000);
        }
        assertTrue(playbackLaunched.get());
        assertTrue(closeFinished.getCount() == 0);
        try {
            gate.runWhileOpen(() -> fail("Playback restarted after close"));
            fail("Playback gate reopened");
        } catch (IllegalStateException expected) { }
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(2, TimeUnit.SECONDS)) throw new AssertionError("Start gate timed out");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new AssertionError(e);
        }
    }
}
