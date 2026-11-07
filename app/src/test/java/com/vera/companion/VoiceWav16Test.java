package com.vera.companion;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Random;
import org.junit.Test;

public final class VoiceWav16Test {
    @Test public void decodesValidMonoPcm16AndCopiesAudio() {
        byte[] wav = wav(1, 16_000, new byte[] {1, 2, 3, 4});
        VoiceWav16 parsed = VoiceWav16.parse(wav);
        assertEquals(16_000, parsed.sampleRate());
        assertEquals(1, parsed.channels());
        assertEquals(2, parsed.frames());
        assertArrayEquals(new byte[] {1, 2, 3, 4}, parsed.pcmCopy());
        wav[44] = 99;
        byte[] leaked = parsed.pcmCopy();
        leaked[0] = 88;
        assertArrayEquals(new byte[] {1, 2, 3, 4}, parsed.pcmCopy());
    }

    @Test public void decodesValidStereoPcm16() {
        VoiceWav16 parsed = VoiceWav16.parse(wav(2, 48_000,
                new byte[] {0, 1, 2, 3, 4, 5, 6, 7}));
        assertEquals(2, parsed.channels());
        assertEquals(2, parsed.frames());
    }

    @Test public void acceptsPlainPcmFormatWithTwoExtraFormatBytes() {
        // Windows SAPI can emit a 46-byte header with fmt size 18, not 44.
        byte[] ordinary = wav(1, 22_050, new byte[] {1, 2, 3, 4});
        byte[] extended = new byte[ordinary.length + 2];
        System.arraycopy(ordinary, 0, extended, 0, 36);
        System.arraycopy(ordinary, 36, extended, 38, ordinary.length - 36);
        put32(extended, 16, 18);
        put32(extended, 4, extended.length - 8);
        VoiceWav16 parsed = VoiceWav16.parse(extended);
        assertEquals(22_050, parsed.sampleRate());
        assertEquals(2, parsed.frames());
        assertArrayEquals(new byte[] {1, 2, 3, 4}, parsed.pcmCopy());
    }

    @Test public void rejectsRiffLengthMismatchAndTrailingData() {
        byte[] valid = wav(1, 16_000, new byte[] {0, 1});
        byte[] trailing = Arrays.copyOf(valid, valid.length + 1);
        rejects(trailing);
        byte[] wrong = valid.clone();
        wrong[4] = 0;
        rejects(wrong);
    }

    @Test public void rejectsUnsupportedFormatsAndInconsistentByteRate() {
        byte[] valid = wav(1, 16_000, new byte[] {0, 1});
        for (int position : new int[] {20, 22, 24, 28, 32, 34}) {
            byte[] mutation = valid.clone();
            mutation[position] ^= 1;
            rejects(mutation);
        }
    }

    @Test public void rejectsMisalignedEmptyAndOversizedPcm() {
        rejects(wav(2, 16_000, new byte[] {0, 1}));
        rejects(wav(1, 16_000, new byte[0]));
        rejects(new byte[VoiceWav16.MAX_WAV_BYTES + 1]);
        rejects(wav(1, 16_000, new byte[16_000 * 2 * 30 + 2]));
    }

    @Test public void acceptsPaddedMetadataChunkAndRejectsMissingPad() {
        byte[] valid = wav(1, 16_000, new byte[] {1, 2});
        byte[] extra = new byte[valid.length + 10];
        System.arraycopy(valid, 0, extra, 0, 12);
        extra[12] = 'J'; extra[13] = 'U'; extra[14] = 'N'; extra[15] = 'K';
        extra[16] = 1;
        extra[20] = 7;
        System.arraycopy(valid, 12, extra, 22, valid.length - 12);
        put32(extra, 4, extra.length - 8);
        assertEquals(1, VoiceWav16.parse(extra).frames());
        byte[] truncated = Arrays.copyOf(extra, extra.length - 1);
        put32(truncated, 4, truncated.length - 8);
        rejects(truncated);
    }

    @Test public void rejectsDuplicateDataChunks() {
        byte[] one = wav(1, 16_000, new byte[] {1, 2});
        byte[] duplicate = Arrays.copyOf(one, one.length + 10);
        System.arraycopy(one, 36, duplicate, one.length, 10);
        put32(duplicate, 4, duplicate.length - 8);
        rejects(duplicate);
    }

    @Test public void boundedMutatedInputsFailClosedWithoutOtherExceptions() {
        Random random = new Random(0x56455241);
        byte[] valid = wav(1, 16_000, new byte[] {1, 2, 3, 4});
        for (int i = 0; i < 1000; i++) {
            byte[] candidate = valid.clone();
            for (int j = 0; j < 1 + random.nextInt(8); j++) {
                candidate[random.nextInt(candidate.length)] = (byte) random.nextInt(256);
            }
            try {
                VoiceWav16.parse(candidate);
            } catch (IllegalArgumentException expected) {
                // Unsupported/corrupt inputs are rejected through the typed boundary.
            }
        }
    }

    private static byte[] wav(int channels, int sampleRate, byte[] pcm) {
        ByteBuffer b = ByteBuffer.allocate(44 + pcm.length).order(ByteOrder.LITTLE_ENDIAN);
        b.put("RIFF".getBytes(StandardCharsets.US_ASCII)).putInt(36 + pcm.length);
        b.put("WAVEfmt ".getBytes(StandardCharsets.US_ASCII)).putInt(16);
        b.putShort((short) 1).putShort((short) channels).putInt(sampleRate);
        b.putInt(sampleRate * channels * 2).putShort((short) (channels * 2)).putShort((short) 16);
        b.put("data".getBytes(StandardCharsets.US_ASCII)).putInt(pcm.length).put(pcm);
        return b.array();
    }

    private static void put32(byte[] bytes, int pos, int value) {
        bytes[pos] = (byte) value;
        bytes[pos + 1] = (byte) (value >>> 8);
        bytes[pos + 2] = (byte) (value >>> 16);
        bytes[pos + 3] = (byte) (value >>> 24);
    }

    private static void rejects(byte[] candidate) {
        try {
            VoiceWav16.parse(candidate);
            fail("Malformed PCM WAV unexpectedly accepted");
        } catch (IllegalArgumentException expected) {
            // expected
        }
    }
}
