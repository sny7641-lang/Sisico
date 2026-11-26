package com.sisico.remote

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

data class Monitor(val left: Int, val top: Int, val width: Int, val height: Int)

/** PC 호스트와의 WebSocket 연결. 콜백은 네트워크 스레드에서 불립니다. */
class RemoteClient(private val host: HostEntry, private val cb: Callback) {

    interface Callback {
        fun onAuthed(pcName: String, monitors: List<Monitor>)
        fun onStream(codec: String, w: Int, h: Int, monW: Int, monH: Int)
        fun onVideo(kind: Int, key: Boolean, data: ByteArray, offset: Int)
        fun onCursor(x: Float, y: Float)
        fun onPong(rttMs: Long)
        fun onClipboard(text: String)
        fun onClosed(reason: String, authFailed: Boolean)
    }

    private val http = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(10, TimeUnit.SECONDS)
        .build()
    private var ws: WebSocket? = null
    @Volatile private var closedReported = false
    @Volatile private var authFailed = false
    @Volatile var authed = false
        private set

    fun connect() {
        val url = "ws://${hostForUrl(host.address)}:${host.port}/"
        ws = http.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) = handleText(text)

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                if (bytes.size < 2) return
                val arr = bytes.toByteArray()
                cb.onVideo(arr[0].toInt(), (arr[1].toInt() and 1) != 0, arr, 2)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                report(if (code == 4001) "비밀번호가 틀렸습니다" else if (code == 4003) "실패가 많아 잠시 막혔습니다 (5분 후 다시)" else "PC가 연결을 끊었습니다", code == 4001)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = report("연결이 끊겼습니다", false)

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) =
                report("연결할 수 없습니다: ${t.message ?: t.javaClass.simpleName}", false)
        })
    }

    private fun hostForUrl(a: String) = if (a.contains(':') && !a.startsWith("[")) "[$a]" else a

    private fun report(reason: String, auth: Boolean) {
        if (closedReported) return
        closedReported = true
        cb.onClosed(if (authFailed) "비밀번호가 틀렸습니다" else reason, auth || authFailed)
        http.dispatcher.executorService.shutdown()
    }

    private fun handleText(text: String) {
        val m = try { JSONObject(text) } catch (e: Exception) { return }
        when (m.optString("t")) {
            "hello" -> {
                val nonce = hexToBytes(m.getString("nonce"))
                val mac = Mac.getInstance("HmacSHA256")
                mac.init(SecretKeySpec(hexToBytes(host.keyHex), "HmacSHA256"))
                val sig = mac.doFinal(nonce).joinToString("") { "%02x".format(it) }
                send(JSONObject().put("t", "auth").put("mac", sig))
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
        }
    }

    fun send(o: JSONObject) {
        ws?.send(o.toString())
    }

    fun msg(type: String, vararg kv: Pair<String, Any>) {
        val o = JSONObject().put("t", type)
        for ((k, v) in kv) o.put(k, v)
        send(o)
    }

    fun close() {
        closedReported = true
        ws?.close(1000, "bye")
        http.dispatcher.executorService.shutdown()
    }

    private fun hexToBytes(s: String) = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
}
