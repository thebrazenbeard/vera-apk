package com.vera.companion;

/** Keep only completed paired turns in the next model request. */
public final class ConversationHistoryPolicy {
    private ConversationHistoryPolicy() {}

    public static boolean replayable(String completionStatus) {
        // The old Ollama path has no completion receipt; preserve its prior
        // behavior. New typed incomplete/unknown replies remain visible in
        // the UI, but are not asserted as finished assistant conversation.
        return "complete".equals(completionStatus)
                || "not_reported".equals(completionStatus);
    }
}
