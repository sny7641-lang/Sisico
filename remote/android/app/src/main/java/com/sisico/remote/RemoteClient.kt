package com.sisico.remote

import android.annotation.SuppressLint
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONArray
import org.json.JSONObject
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

data class Monitor(val left: Int, val top: Int, val width: Int, val height: Int)

/**
 * PC 호스트와의 암호화(wss) 연결. 콜백은 네트워크 스레드에서 불립니다.
 *
 * PC 인증서는 자체 서명이라 일반 인증서 검사 대신 '지문 고정'을 씁니다:
 * 등록할 때 사용자가 확인한 지문(host.pin)과 다르면 키를 보내지 않고 바로 끊습니다.
 * pairing=true 이면 등록 과정: 지문과 salt 를 onPairHello 로 알려 주고 sendAuth 를 기다립니다.
 */
class RemoteClient(private val host: HostEntry, private val cb: Callback, private val pairing: Boolean = false) {

    interface Callback {
        fun onAuthed(pcName: String, monitors: List<Monitor>)
        fun onStream(codec: String, w: Int, h: Int, monW: Int, monH: Int) {}
        fun onVideo(kind: Int, key: Boolean, data: ByteArray, offset: Int) {}
        fun onCursor(x: Float, y: Float) {}
        fun onPong(rttMs: Long) {}
        fun onClipboard(text: String) {}
        fun onClosed(reason: String, authFailed: Boolean)
        fun onOther(m: JSONObject) {}
        fun onPairHello(fingerprint: String, salt: String, iterations: Int, pcName: String) {}
    }

    private val http: OkHttpClient
    private var ws: WebSocket? = null
    @Volatile private var closedReported = false
    @Volatile private var authFailed = false
    @Volatile private var fingerprint = ""
    @Volatile private var pinMismatch = false
    @Volatile var authed = false
        private set

    init {
        // 자체 서명 인증서를 받아들이되, 아래 onOpen 에서 지문으로 직접 확인
        @SuppressLint("CustomX509TrustManager")
        val trustPinned = object : X509TrustManager {
            @SuppressLint("TrustAllX509TrustManager")
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
            @SuppressLint("TrustAllX509TrustManager")
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
                if (chain.isNullOrEmpty()) throw java.security.cert.CertificateException("no certificate")
                // TLS 연결이 만들어지기 전에 지문을 확인: 다르면 여기서 연결 자체를 거부
                val fp = HostStore.sha256Hex(chain[0].encoded)
                fingerprint = fp
                if (!pairing && fp != host.pin) {
                    pinMismatch = true
                    throw java.security.cert.CertificateException("certificate fingerprint mismatch")
                }
            }
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }
        val ssl = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustPinned), null) }
        http = OkHttpClient.Builder()
            .sslSocketFactory(ssl.socketFactory, trustPinned)
            .hostnameVerifier { _, _ -> true }
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .pingInterval(10, TimeUnit.SECONDS)
            .build()
    }

    fun connect() {
        val url = "wss://${hostForUrl(host.address)}:${host.port}/"
        ws = http.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                // 지문 확인은 checkServerTrusted 에서 이미 끝남. 혹시 모를 경우를 위해 한 번 더.
                if (fingerprint.isEmpty() || (!pairing && fingerprint != host.pin)) fail(webSocket, mismatchMessage())
            }

            override fun onMessage(webSocket: WebSocket, text: String) = handleText(text)

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                if (bytes.size < 2 || !authed) return
                val arr = bytes.toByteArray()
                cb.onVideo(arr[0].toInt(), (arr[1].toInt() and 1) != 0, arr, 2)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                report(when (code) {
                    4001 -> "비밀번호가 틀렸습니다"
                    4003 -> "실패가 많아 잠시 막혔습니다 (5분 후 다시)"
                    else -> "PC가 연결을 끊었습니다"
                }, code == 4001)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = report("연결이 끊겼습니다", false)

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) =
                if (pinMismatch) report(mismatchMessage(), true) else report("연결할 수 없습니다: ${t.message ?: t.javaClass.simpleName}\n\n" +
                    "PC 프로그램이 최신 버전인지(암호화 연결), 주소와 포트가 맞는지 확인하세요.", false)
        })
    }

    private fun mismatchMessage() =
        "보안 경고: 이 주소의 PC 인증서가 등록할 때와 다릅니다.\n\n" +
            "다른 기기가 내 PC인 척하고 있을 수 있어 연결하지 않았습니다.\n" +
            "PC 프로그램을 새로 설치했거나 설정을 지웠다면, PC 목록에서 길게 눌러 '수정'으로 다시 등록하세요.\n\n" +
            "지금 받은 지문: ${HostStore.shortFp(fingerprint)}"

    private fun fail(w: WebSocket, reason: String) {
        report(reason, true)
        w.cancel()
    }

    private fun hostForUrl(a: String) = if (a.contains(':') && !a.startsWith("[")) "[$a]" else a

    private fun report(reason: String, auth: Boolean) {
        if (closedReported) return
        closedReported = true
        cb.onClosed(if (authFailed) "비밀번호가 틀렸습니다" else reason, auth || authFailed)
        http.dispatcher.executorService.shutdown()
    }

    /** 등록 과정에서 사용자가 지문을 확인한 뒤 호출 */
    fun sendAuth(keyHex: String) = send(JSONObject().put("t", "auth").put("k", keyHex))

    private fun handleText(text: String) {
        val m = try { JSONObject(text) } catch (e: Exception) { return }
        when (m.optString("t")) {
            "hello" -> {
                if (fingerprint.isEmpty() || closedReported) return
                if (pairing) cb.onPairHello(fingerprint, m.optString("salt"), m.optInt("iter"), m.optString("name"))
                else sendAuth(host.keyHex)
            }
            "ok" -> {
                authed = true
                val arr = m.optJSONArray("monitors") ?: JSONArray()
                val mons = (0 until arr.length()).map {
                    val o = arr.getJSONObject(it)
                    Monitor(o.optInt("left"), o.optInt("top"), o.optInt("width"), o.optInt("height"))
                }
                cb.onAuthed(m.optString("name"), mons)
            }
            "err" -> authFailed = true
            "stream" -> cb.onStream(m.getString("codec"), m.getInt("w"), m.getInt("h"), m.optInt("mw"), m.optInt("mh"))
            "cur" -> cb.onCursor(m.getDouble("x").toFloat(), m.getDouble("y").toFloat())
            "pong" -> cb.onPong(System.currentTimeMillis() - m.optLong("ts"))
            "clip" -> cb.onClipboard(m.optString("s"))
            else -> if (authed) cb.onOther(m)
        }
    }

    fun send(o: JSONObject) {
        ws?.send(o.toString())
    }

    fun msg(type: String, vararg kv: Pair<String, Any>) {
        if (!authed) return
        val o = JSONObject().put("t", type)
        for ((k, v) in kv) o.put(k, v)
        send(o)
    }

    fun sendBinary(b: ByteArray): Boolean = ws?.send(b.toByteString()) ?: false

    /** 아직 보내지 못하고 쌓여 있는 바이트 (파일 보낼 때 속도 조절용) */
    fun queued(): Long = ws?.queueSize() ?: 0L

    fun close() {
        closedReported = true
        ws?.close(1000, "bye")
        http.dispatcher.executorService.shutdown()
    }
}
