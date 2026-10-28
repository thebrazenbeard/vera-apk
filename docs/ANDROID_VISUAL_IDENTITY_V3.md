# Vera Companion 0.2.2 — visual identity and model transparency

The v0.2.1 client included the owner's original OneDrive wallpaper assets, but then
obscured them under Color.argb(220, 13, 18, 29), an 86% dark overlay. It also rendered
the conversation as unstyled multiline text. This revision corrects those regressions
without opening additional network surfaces.

- Original portrait and landscape assets remain embedded as drawable WebP resources.
  The global overlay is reduced to 95/255, allowing the artwork to remain visible;
  messages and status are separately backed by opaque/semitransparent panels.
- Restores Vera's distinctive serif masthead and ruby/plum palette; user and model
  messages use separate, readable rounded cards and clear speaker labels.
- Connection credentials are hidden by default when paired, and can be accessed via
  the CONNECTION SETTINGS disclosure. Existing private preferences and security
  controls are unchanged.
- Default inference model is the *installed* `vera-local:latest` when present;
  an explicitly selected model is preserved across authenticated reconnects.
  Without Vera available, selection falls back to the first returned model.
- Reply cards label the actual selected model. This is not a claim that the model
  is independently pretrained; the local `vera-local:latest` currently reports
  Qwen3 4B architecture in `ollama show`.
- Safe-area composer, in-place orientation changes, and foreground reconnection
  behavior from 0.2.1 are preserved.

Verification: Android model preference unit cases fail before implementation and pass
after. Branding regression tests confirm overlay, bubble content, settings disclosure
and default selection source contract. Local Gradle compile/test/APK build are required
before release; real Galaxy screenshots and input tests remain separate acceptance.
