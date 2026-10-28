package com.vera.companion;

/** Screen-edge spacing measured in physical pixels. */
public final class SafeAreaPadding {
    private SafeAreaPadding() {}

    public static int bottom(int base, int navigationBar, int keyboard) {
        return base;
    }
}
