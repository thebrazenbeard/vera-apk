package com.vera.companion;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Handler;
import android.os.Looper;

/**
 * User-initiated, local speaker output. Call solely from a visible user playback action.
 * No network, capture, storage, account, or background replay is implemented here.
 * Release from the owning Activity's onStop()/onDestroy(), or by calling close().
 */
public final class VoiceWavePlayer implements AutoCloseable {
    private final AudioManager audioManager;
    private final AudioFocusRequest focusRequest;
    private AudioTrack track;
    private boolean closed;

    private VoiceWavePlayer(AudioManager audioManager, AudioFocusRequest focusRequest) {
        this.audioManager = audioManager;
        this.focusRequest = focusRequest;
    }

    /** Does not create authority: callers must bind this solely to a real UI tap. */
    public static VoiceWavePlayer playFromUserTap(Context context, byte[] wave) {
        VoiceWav16 parsed = VoiceWav16.parse(wave);
        AudioManager manager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (manager == null) throw new IllegalStateException("Audio service unavailable");

        AudioAttributes attributes = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANT)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build();
        final VoiceWavePlayer[] reference = new VoiceWavePlayer[1];
        AudioFocusRequest focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                .setAudioAttributes(attributes)
                .setOnAudioFocusChangeListener(change -> {
                    if (change == AudioManager.AUDIOFOCUS_LOSS
                            || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT
                            || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK) {
                        VoiceWavePlayer active = reference[0];
                        if (active != null) active.close();
                    }
                })
                .build();
        VoiceWavePlayer player = new VoiceWavePlayer(manager, focus);
        reference[0] = player;

        if (manager.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            throw new IllegalStateException("Audio focus denied");
        }
        try {
            byte[] pcm = parsed.pcmCopy();
            int outputMask = parsed.channels() == 1
                    ? AudioFormat.CHANNEL_OUT_MONO : AudioFormat.CHANNEL_OUT_STEREO;
            AudioFormat format = new AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(parsed.sampleRate())
                    .setChannelMask(outputMask)
                    .build();
            AudioTrack candidate = new AudioTrack.Builder()
                    .setAudioAttributes(attributes)
                    .setAudioFormat(format)
                    .setBufferSizeInBytes(pcm.length)
                    .setTransferMode(AudioTrack.MODE_STATIC)
                    .build();
            player.track = candidate;
            if (candidate.getState() != AudioTrack.STATE_INITIALIZED) {
                throw new IllegalStateException("AudioTrack initialization failed");
            }
            int written = candidate.write(pcm, 0, pcm.length, AudioTrack.WRITE_BLOCKING);
            if (written != pcm.length) {
                throw new IllegalStateException("AudioTrack PCM write incomplete: " + written);
            }
            candidate.setNotificationMarkerPosition(parsed.frames());
            candidate.setPlaybackPositionUpdateListener(new AudioTrack.OnPlaybackPositionUpdateListener() {
                @Override public void onMarkerReached(AudioTrack ignored) { player.close(); }
                @Override public void onPeriodicNotification(AudioTrack ignored) { }
            }, new Handler(Looper.getMainLooper()));
            candidate.play();
            return player;
        } catch (RuntimeException | Error failure) {
            player.close();
            throw failure;
        }
    }

    /** Safe to call repeatedly, including after focus loss, playback completion, and UI teardown. */
    @Override public synchronized void close() {
        if (closed) return;
        closed = true;
        AudioTrack current = track;
        track = null;
        if (current != null) {
            try {
                if (current.getPlayState() == AudioTrack.PLAYSTATE_PLAYING) current.stop();
            } catch (IllegalStateException ignored) {
                // Native playback may already have ended or been invalidated.
            } finally {
                current.release();
            }
        }
        audioManager.abandonAudioFocusRequest(focusRequest);
    }
}
