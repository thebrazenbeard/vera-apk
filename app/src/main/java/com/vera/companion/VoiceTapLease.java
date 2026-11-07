package com.vera.companion;

/** One active playback binding per dedicated UI control; fail-closed on overlap. */
final class VoiceTapLease {
    private Object owner;

    synchronized boolean claim(Object candidate) {
        if (candidate == null || owner != null) return false;
        owner = candidate;
        return true;
    }

    synchronized boolean release(Object candidate) {
        if (owner != candidate || candidate == null) return false;
        owner = null;
        return true;
    }
}
