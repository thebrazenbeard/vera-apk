package com.vera.companion;
import java.util.List;
import java.util.Locale;
public final class ModelPreference {
    private ModelPreference() {}
    public static int choose(List<String> models, String previous) {
        if (models == null || models.isEmpty()) return -1;
        if (previous != null && !previous.isEmpty() && models.contains(previous)) return models.indexOf(previous);
        int exact = models.indexOf("vera-local:latest");
        if (exact >= 0) return exact;
        for (int i = 0; i < models.size(); i++) {
            String n = models.get(i).toLowerCase(Locale.ROOT);
            if (n.equals("vera") || n.startsWith("vera-") || n.startsWith("vera:") || n.startsWith("vera_")) return i;
        }
        return 0;
    }
}
