package com.vera.companion;

import java.util.Arrays;

/** A bounded, uncompressed PCM16 RIFF/WAVE payload suitable for local speech playback. */
public final class VoiceWav16 {
    public static final int MAX_WAV_BYTES = 6_000_000;
    public static final int MAX_SECONDS = 30;

    private final int sampleRate;
    private final int channels;
    private final int frames;
    private final byte[] pcm;

    private VoiceWav16(int sampleRate, int channels, int frames, byte[] pcm) {
        this.sampleRate = sampleRate;
        this.channels = channels;
        this.frames = frames;
        this.pcm = pcm;
    }

    public int sampleRate() { return sampleRate; }
    public int channels() { return channels; }
    public int frames() { return frames; }
    public byte[] pcmCopy() { return pcm.clone(); }

    /** Parse only a tightly bounded subset. Invalid or unsupported input fails closed. */
    public static VoiceWav16 parse(byte[] wave) {
        if (wave == null || wave.length < 44 || wave.length > MAX_WAV_BYTES) {
            throw new IllegalArgumentException("WAV size outside accepted bounds");
        }
        if (!ascii(wave, 0, "RIFF") || !ascii(wave, 8, "WAVE")
                || u32(wave, 4) != wave.length - 8L) {
            throw new IllegalArgumentException("Invalid RIFF/WAVE envelope");
        }

        int sampleRate = 0;
        int channels = 0;
        int blockAlign = 0;
        int dataOffset = -1;
        int dataLength = -1;
        boolean fmtFound = false;
        boolean dataFound = false;
        long cursor = 12;
        while (cursor < wave.length) {
            if (wave.length - cursor < 8L) {
                throw new IllegalArgumentException("Truncated WAV chunk header");
            }
            int offset = (int) cursor;
            long chunkSize = u32(wave, offset + 4);
            long contentStart = cursor + 8;
            long next = contentStart + chunkSize + (chunkSize & 1L);
            if (next > wave.length) {
                throw new IllegalArgumentException("Truncated WAV chunk data or padding");
            }
            if (ascii(wave, offset, "fmt ")) {
                if (fmtFound || chunkSize < 16) {
                    throw new IllegalArgumentException("Duplicate or truncated WAV format");
                }
                fmtFound = true;
                int start = (int) contentStart;
                int code = u16(wave, start);
                channels = u16(wave, start + 2);
                long rate = u32(wave, start + 4);
                long byteRate = u32(wave, start + 8);
                blockAlign = u16(wave, start + 12);
                int bits = u16(wave, start + 14);
                if (code != 1 || (channels != 1 && channels != 2)
                        || rate < 8_000 || rate > 48_000 || bits != 16
                        || blockAlign != channels * 2 || byteRate != rate * blockAlign) {
                    throw new IllegalArgumentException("Unsupported PCM WAV format");
                }
                sampleRate = (int) rate;
            } else if (ascii(wave, offset, "data")) {
                if (dataFound || chunkSize == 0 || chunkSize > MAX_WAV_BYTES) {
                    throw new IllegalArgumentException("Duplicate or empty WAV audio data");
                }
                dataFound = true;
                dataOffset = (int) contentStart;
                dataLength = (int) chunkSize;
            }
            cursor = next;
        }
        if (!fmtFound || !dataFound || dataLength % blockAlign != 0) {
            throw new IllegalArgumentException("Missing or unaligned PCM data");
        }
        long frames = dataLength / blockAlign;
        if (frames > (long) sampleRate * MAX_SECONDS) {
            throw new IllegalArgumentException("Speech exceeds playback duration bound");
        }
        return new VoiceWav16(sampleRate, channels, (int) frames,
                Arrays.copyOfRange(wave, dataOffset, dataOffset + dataLength));
    }

    private static boolean ascii(byte[] bytes, int offset, String token) {
        for (int i = 0; i < token.length(); i++) {
            if (bytes[offset + i] != (byte) token.charAt(i)) return false;
        }
        return true;
    }

    private static int u16(byte[] bytes, int start) {
        return (bytes[start] & 255) | ((bytes[start + 1] & 255) << 8);
    }

    private static long u32(byte[] bytes, int start) {
        return (bytes[start] & 255L) | ((bytes[start + 1] & 255L) << 8)
                | ((bytes[start + 2] & 255L) << 16) | ((bytes[start + 3] & 255L) << 24);
    }
}
