package com.vera.companion;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.Test;

public final class VoiceTapSessionTest {
    @Test public void noPlaybackUntilVisibleTap() {
        AtomicInteger starts = new AtomicInteger();
        VoiceTapSession session = new VoiceTapSession(() -> {
            starts.incrementAndGet();
            return () -> { };
        });
        assertEquals(0, starts.get());
        assertFalse(session.onVisibleTap(false));
        assertEquals(0, starts.get());
        assertTrue(session.onVisibleTap(true));
        assertEquals(1, starts.get());
        session.close();
    }

    @Test public void repeatTapClosesPreviousPlaybackBeforeRestart() {
        StringBuilder events = new StringBuilder();
        VoiceTapSession session = new VoiceTapSession(() -> {
            events.append('S');
            return () -> events.append('C');
        });
        assertTrue(session.onVisibleTap(true));
        assertTrue(session.onVisibleTap(true));
        assertEquals("SCS", events.toString());
        session.close();
        session.close();
        assertEquals("SCSC", events.toString());
        assertFalse(session.onVisibleTap(true));
        assertEquals("SCSC", events.toString());
    }

    @Test public void failedLaunchLeavesNoReplayHandle() {
        AtomicInteger attempts = new AtomicInteger();
        VoiceTapSession session = new VoiceTapSession(() -> {
            attempts.incrementAndGet();
            throw new IllegalStateException("focus denied");
        });
        try {
            session.onVisibleTap(true);
            fail("Launch failure must propagate");
        } catch (IllegalStateException expected) {
            assertEquals("focus denied", expected.getMessage());
        }
        session.close();
        assertFalse(session.onVisibleTap(true));
        assertEquals(1, attempts.get());
    }

    @Test public void closeWaitsForInFlightTapThenReleasesHandle() throws Exception {
        CountDownLatch launchEntered = new CountDownLatch(1);
        CountDownLatch allowLaunch = new CountDownLatch(1);
        CountDownLatch closeFinished = new CountDownLatch(1);
        AtomicInteger releases = new AtomicInteger();
        VoiceTapSession session = new VoiceTapSession(() -> {
            launchEntered.countDown();
            try {
                if (!allowLaunch.await(2, TimeUnit.SECONDS)) throw new AssertionError("launch wait timed out");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new AssertionError(e);
            }
            return releases::incrementAndGet;
        });
        Thread tap = new Thread(() -> session.onVisibleTap(true));
        Thread close = new Thread(() -> {
            session.close();
            closeFinished.countDown();
        });
        tap.start();
        assertTrue("launch started", launchEntered.await(2, TimeUnit.SECONDS));
        close.start();
        assertFalse("close cannot finish before startup exits", closeFinished.await(50, TimeUnit.MILLISECONDS));
        allowLaunch.countDown();
        tap.join(2000);
        close.join(2000);
        assertFalse("tap thread ended", tap.isAlive());
        assertFalse("close thread ended", close.isAlive());
        assertEquals(1, releases.get());
        assertFalse(session.onVisibleTap(true));
    }

    @Test public void priorHandleReentrantCloseCancelsReplacement() {
        final VoiceTapSession[] reference = new VoiceTapSession[1];
        AtomicInteger launches = new AtomicInteger();
        VoiceTapSession session = new VoiceTapSession(() -> {
            launches.incrementAndGet();
            return reference[0]::close;
        });
        reference[0] = session;
        assertTrue(session.onVisibleTap(true));
        assertFalse("reentrant stop must win", session.onVisibleTap(true));
        assertFalse(session.onVisibleTap(true));
        assertEquals(1, launches.get());
    }

    @Test public void launcherReentrantCloseReleasesReturnedHandle() {
        final VoiceTapSession[] reference = new VoiceTapSession[1];
        AtomicInteger releases = new AtomicInteger();
        VoiceTapSession session = new VoiceTapSession(() -> {
            reference[0].close();
            return releases::incrementAndGet;
        });
        reference[0] = session;
        assertFalse("stop during launch must win", session.onVisibleTap(true));
        assertFalse(session.onVisibleTap(true));
        assertEquals(1, releases.get());
    }
}
