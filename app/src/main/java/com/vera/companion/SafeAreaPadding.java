package com.vera.companion;

/** Insets are physical pixels; the largest bottom obstruction wins. */
public final class SafeAreaPadding {
    private SafeAreaPadding() {}

    public static int top(int base, int statusBar) {
        return Math.max(0, base) + Math.max(0, statusBar);
    }

    public static int bottom(int base, int navigationBar, int keyboard) {
        return Math.max(0, base) + Math.max(0, Math.max(navigationBar, keyboard));
    }
}
