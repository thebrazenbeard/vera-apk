package com.vera.companion;

import java.util.Objects;

public final class CapabilityGate {
    private CapabilityGate() {}

    public record EffectRequest(String effectId, String authorizationToken) {
        public EffectRequest {
            effectId = Objects.requireNonNull(effectId, "effectId").trim();
            authorizationToken = authorizationToken == null ? "" : authorizationToken.trim();
            if (effectId.isEmpty()) {
                throw new IllegalArgumentException("effectId must not be empty");
            }
        }
    }

    public static boolean maySubmit(EffectRequest request) {
        Objects.requireNonNull(request, "request");
        return !request.authorizationToken().isEmpty();
    }
}
