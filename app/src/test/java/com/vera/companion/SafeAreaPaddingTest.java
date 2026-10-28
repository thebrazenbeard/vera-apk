package com.vera.companion;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

public final class SafeAreaPaddingTest {
    @Test public void composerClearsBottomNavigationBar() {
        assertEquals(48, SafeAreaPadding.bottom(12, 36, 0));
    }
    @Test public void composerMovesAboveKeyboardRatherThanStackingInsets() {
        assertEquals(312, SafeAreaPadding.bottom(12, 36, 300));
    }
    @Test public void noInsetsKeepsBaseSpacing() {
        assertEquals(12, SafeAreaPadding.bottom(12, 0, 0));
    }
    @Test public void invalidInsetsNeverReduceSpacing() {
        assertEquals(12, SafeAreaPadding.bottom(12, -25, -3));
    }
}
