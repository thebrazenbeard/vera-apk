package com.vera.companion;

import org.junit.Test;
import java.util.Arrays;
import java.util.Collections;
import static org.junit.Assert.assertEquals;

public class ModelPreferenceTest {
    @Test public void veraLocalWinsOverCoderFirst() {
        assertEquals(2, ModelPreference.choose(Arrays.asList(
            "qwen2.5-coder:1.5b-instruct-q8_0", "gemma3:1b", "vera-local:latest"), ""));
    }
    @Test public void keepsExplicitExistingSelectionAcrossReconnect() {
        assertEquals(0, ModelPreference.choose(Arrays.asList(
            "qwen2.5-coder:1.5b-instruct-q8_0", "vera-local:latest"),
            "qwen2.5-coder:1.5b-instruct-q8_0"));
    }
    @Test public void fallsBackToNamedVeraModel() {
        assertEquals(1, ModelPreference.choose(Arrays.asList("qwen3:4b", "vera-v2:latest"), ""));
    }
    @Test public void fallbackFirstOnlyWhenNoVeraModel() {
        assertEquals(0, ModelPreference.choose(Arrays.asList("qwen3:4b", "gemma3:1b"), ""));
    }
    @Test public void emptyInventoryReturnsNoSelection() {
        assertEquals(-1, ModelPreference.choose(Collections.emptyList(), ""));
    }
}
