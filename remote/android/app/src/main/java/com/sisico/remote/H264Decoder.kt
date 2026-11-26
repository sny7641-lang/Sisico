package com.sisico.remote

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import android.view.Surface
import java.nio.ByteBuffer
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * H.264(Annex-B) 패킷을 하드웨어 디코더(MediaCodec)로 풀어 Surface 에 바로 그립니다.
 * 첫 키프레임에서 SPS/PPS 를 꺼내 디코더를 설정합니다.
 */
class H264Decoder(
    private val surface: Surface,
    private val width: Int,
    private val height: Int,
    private val requestKeyFrame: () -> Unit,
) {
    private class Packet(val data: ByteArray, val offset: Int, val key: Boolean)

    private val queue = LinkedBlockingQueue<Packet>()
    @Volatile private var running = true
    private var codec: MediaCodec? = null
    private var waitingForKey = true
    private val thread = Thread({ loop() }, "h264-decoder").apply { start() }

    /** 화면에 그려진 프레임 수 (통계용). */
    @Volatile var renderedFrames = 0L

    fun offer(data: ByteArray, offset: Int, key: Boolean) {
        if (queue.size > 20) {      // 너무 밀리면 버리고 새 키프레임부터 다시
            queue.clear()
            waitingForKey = true
            requestKeyFrame()
        }
        queue.offer(Packet(data, offset, key))
    }

    fun release() {
        running = false
        thread.interrupt()
        try { thread.join(500) } catch (_: InterruptedException) {}
    }

    private fun loop() {
        val info = MediaCodec.BufferInfo()
        try {
            while (running) {
                val p = queue.poll(5, TimeUnit.MILLISECONDS)
                if (p != null) {
                    if (waitingForKey) {
                        if (!p.key) continue
                        if (codec == null && !startCodec(p)) { requestKeyFrame(); continue }
                        waitingForKey = false
                    }
                    feed(p)
                }
                drain(info)
            }
        } catch (_: InterruptedException) {
        } catch (e: Exception) {
            Log.w(TAG, "decoder error", e)
        } finally {
            stopCodec()
        }
    }

    private fun startCodec(p: Packet): Boolean {
        val (sps, pps) = findParams(p.data, p.offset)
        if (sps == null || pps == null) return false
        return try {
            val fmt = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height)
            fmt.setByteBuffer("csd-0", ByteBuffer.wrap(sps))
            fmt.setByteBuffer("csd-1", ByteBuffer.wrap(pps))
            if (Build.VERSION.SDK_INT >= 30) fmt.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
            fmt.setInteger(MediaFormat.KEY_PRIORITY, 0)
            val c = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            c.configure(fmt, surface, null, 0)
            c.start()
            codec = c
            true
        } catch (e: Exception) {
            Log.w(TAG, "codec start failed", e)
            stopCodec()
            false
        }
    }

    private fun feed(p: Packet) {
        val c = codec ?: return
        try {
            val idx = c.dequeueInputBuffer(20_000)
            if (idx < 0) { waitingForKey = true; requestKeyFrame(); return }  // 버퍼 없음 → 이 프레임은 버림
            val buf = c.getInputBuffer(idx)!!
            buf.clear()
            val len = p.data.size - p.offset
            buf.put(p.data, p.offset, len)
            c.queueInputBuffer(idx, 0, len, System.nanoTime() / 1000, 0)
        } catch (e: IllegalStateException) {
            Log.w(TAG, "feed failed, restarting", e)
            stopCodec(); waitingForKey = true; requestKeyFrame()
        }
    }

    private fun drain(info: MediaCodec.BufferInfo) {
        val c = codec ?: return
        try {
            while (true) {
                val idx = c.dequeueOutputBuffer(info, 0)
                if (idx >= 0) {
                    c.releaseOutputBuffer(idx, true)
                    renderedFrames++
                } else if (idx == MediaCodec.INFO_TRY_AGAIN_LATER) {
                    break
                }
            }
        } catch (e: IllegalStateException) {
            stopCodec(); waitingForKey = true; requestKeyFrame()
        }
    }

    private fun stopCodec() {
        codec?.let {
            try { it.stop() } catch (_: Exception) {}
            try { it.release() } catch (_: Exception) {}
        }
        codec = null
    }

    companion object {
        private const val TAG = "H264Decoder"

        /** Annex-B 스트림에서 SPS(7), PPS(8) NAL 을 시작코드 포함해 꺼냅니다. */
        fun findParams(d: ByteArray, from: Int): Pair<ByteArray?, ByteArray?> {
            val starts = ArrayList<Int>()   // NAL 시작 코드 위치
            var i = from
            while (i + 3 < d.size) {
                if (d[i].toInt() == 0 && d[i + 1].toInt() == 0) {
                    if (d[i + 2].toInt() == 1) { starts.add(i); i += 3; continue }
                    if (d[i + 2].toInt() == 0 && d[i + 3].toInt() == 1) { starts.add(i); i += 4; continue }
                }
                i++
            }
            var sps: ByteArray? = null
            var pps: ByteArray? = null
            for ((n, s) in starts.withIndex()) {
                val hdr = if (d[s + 2].toInt() == 1) s + 3 else s + 4
                if (hdr >= d.size) continue
                val end = if (n + 1 < starts.size) starts[n + 1] else d.size
                when (d[hdr].toInt() and 0x1F) {
                    7 -> if (sps == null) sps = d.copyOfRange(s, end)
                    8 -> if (pps == null) pps = d.copyOfRange(s, end)
                }
            }
            return sps to pps
        }
    }
}
