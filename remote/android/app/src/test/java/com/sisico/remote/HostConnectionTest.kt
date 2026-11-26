package com.sisico.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * 실제 PC 호스트에 붙여 보는 통합 테스트. 호스트를 띄운 뒤에만 실행됩니다:
 *   python sisico_remote_host.py --test --password ci-test-pass
 *   SISICO_TEST_HOST=127.0.0.1 ./gradlew testDebugUnitTest
 */
class HostConnectionTest {
    private val addr = System.getenv("SISICO_TEST_HOST")

    private fun pairThenConnect(password: String): Triple<String, String, Int> {
        // 1) 등록: 지문과 salt 받기 → 키 만들어 로그인
        var pin = ""; var key = ""; var result = ""
        val done = CountDownLatch(1)
        lateinit var c: RemoteClient
        c = RemoteClient(HostEntry("t", "", addr!!, 8765, ""), object : RemoteClient.Callback {
            override fun onPairHello(fingerprint: String, salt: String, iterations: Int, pcName: String) {
                pin = fingerprint
                key = HostStore.deriveKey(password, salt, iterations)
                c.sendAuth(key)
            }
            override fun onAuthed(pcName: String, monitors: List<Monitor>) { result = "ok"; c.close(); done.countDown() }
            override fun onClosed(reason: String, authFailed: Boolean) { result = "closed:$authFailed"; done.countDown() }
        }, pairing = true)
        c.connect()
        assertTrue(done.await(20, TimeUnit.SECONDS))
        if (result != "ok") return Triple(result, "", 0)

        // 2) 저장된 지문·키로 일반 접속 → 화면 받기
        var frames = 0; var status = ""
        val got = CountDownLatch(1)
        lateinit var c2: RemoteClient
        c2 = RemoteClient(HostEntry("t", "", addr, 8765, key, pin), object : RemoteClient.Callback {
            override fun onAuthed(pcName: String, monitors: List<Monitor>) {
                c2.msg("start", "codec" to "h264", "mon" to 0, "fps" to 30, "maxw" to 640, "kbps" to 2000)
            }
            override fun onVideo(kind: Int, key: Boolean, data: ByteArray, offset: Int) {
                if (kind == 1 && ++frames >= 10) { status = "frames"; c2.close(); got.countDown() }
            }
            override fun onClosed(reason: String, authFailed: Boolean) { status = reason; got.countDown() }
        })
        c2.connect()
        assertTrue(got.await(20, TimeUnit.SECONDS))
        return Triple(result, status, frames)
    }

    @Test
    fun pairsAndStreams() {
        assumeTrue(addr != null)
        val (r, s, n) = pairThenConnect("ci-test-pass")
        assertEquals("ok", r); assertEquals("frames", s); assertTrue(n >= 10)
    }

    @Test
    fun wrongPasswordIsRejected() {
        assumeTrue(addr != null)
        assertEquals("closed:true", pairThenConnect("wrong-password").first)
    }

    @Test
    fun wrongPinIsRefused() {
        assumeTrue(addr != null)
        var reason = ""; var auth = false
        val done = CountDownLatch(1)
        RemoteClient(HostEntry("t", "", addr!!, 8765, "00", "deadbeef"), object : RemoteClient.Callback {
            override fun onAuthed(pcName: String, monitors: List<Monitor>) { done.countDown() }
            override fun onClosed(r: String, a: Boolean) { reason = r; auth = a; done.countDown() }
        }).connect()
        assertTrue(done.await(20, TimeUnit.SECONDS))
        assertTrue(reason, reason.startsWith("보안 경고") && auth)
    }
}
