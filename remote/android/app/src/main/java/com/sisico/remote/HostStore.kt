package com.sisico.remote

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * 저장된 PC 한 대.
 *  keyHex: PBKDF2(비밀번호, PC의 salt) — 비밀번호 자체는 저장하지 않음
 *  pin:    PC 인증서 지문(sha256). 접속할 때마다 같은지 확인해 가짜 PC를 막음. 비어 있으면 다시 등록 필요.
 */
data class HostEntry(
    val id: String,
    val name: String,
    val address: String,
    val port: Int,
    val keyHex: String,
    val pin: String = "",
) {
    val needsPairing get() = pin.isEmpty() || keyHex.isEmpty()

    fun toJson() = JSONObject()
        .put("id", id).put("name", name).put("address", address).put("port", port)
        .put("key2", keyHex).put("pin", pin)

    companion object {
        // 예전 버전의 "key"(sha256) 는 더 이상 쓰지 않음 → 다시 등록하도록 비워 둠
        fun fromJson(o: JSONObject) = HostEntry(
            o.getString("id"), o.optString("name"), o.getString("address"),
            o.optInt("port", 8765), o.optString("key2"), o.optString("pin"),
        )
    }
}

object HostStore {
    private const val PREFS = "hosts"

    /** PBKDF2-HMAC-SHA256 (32바이트). 한글 비밀번호도 PC와 똑같이 UTF-8 로 처리하려고 직접 구현. */
    fun deriveKey(pw: String, saltHex: String, iterations: Int): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(pw.toByteArray(Charsets.UTF_8), "HmacSHA256"))
        mac.update(hexToBytes(saltHex))
        mac.update(byteArrayOf(0, 0, 0, 1))
        var u = mac.doFinal()
        val t = u.copyOf()
        for (i in 1 until iterations) {
            u = mac.doFinal(u)
            for (j in t.indices) t[j] = (t[j].toInt() xor u[j].toInt()).toByte()
        }
        return toHex(t)
    }

    fun toHex(b: ByteArray) = b.joinToString("") { "%02x".format(it) }
    fun hexToBytes(s: String) = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    fun sha256Hex(b: ByteArray) = toHex(MessageDigest.getInstance("SHA-256").digest(b))

    /** 눈으로 비교할 지문: 앞 16자리를 4자리씩 (PC 창과 같은 모양) */
    fun shortFp(fp: String) = fp.take(16).uppercase().chunked(4).joinToString("-")

    fun load(ctx: Context): MutableList<HostEntry> {
        val raw = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("list", "[]")
        val arr = JSONArray(raw)
        return MutableList(arr.length()) { HostEntry.fromJson(arr.getJSONObject(it)) }
    }

    fun save(ctx: Context, list: List<HostEntry>) {
        val arr = JSONArray()
        list.forEach { arr.put(it.toJson()) }
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("list", arr.toString()).apply()
    }

    fun get(ctx: Context, id: String) = load(ctx).firstOrNull { it.id == id }
}

/** 화질·조작 설정 (앱 전체 공통). */
class Settings(ctx: Context) {
    private val p = ctx.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var codec: String
        get() = p.getString("codec", "h264")!!
        set(v) = p.edit().putString("codec", v).apply()
    var fps: Int
        get() = p.getInt("fps", 30)
        set(v) = p.edit().putInt("fps", v).apply()
    var maxSide: Int
        get() = p.getInt("maxSide", 1920)
        set(v) = p.edit().putInt("maxSide", v).apply()
    var kbps: Int
        get() = p.getInt("kbps", 6000)
        set(v) = p.edit().putInt("kbps", v).apply()
    var jpegQuality: Int
        get() = p.getInt("q", 70)
        set(v) = p.edit().putInt("q", v).apply()
    var trackpad: Boolean
        get() = p.getBoolean("trackpad", true)
        set(v) = p.edit().putBoolean("trackpad", v).apply()
    var speed: Float
        get() = p.getFloat("speed", 1.3f)
        set(v) = p.edit().putFloat("speed", v).apply()
    var showStats: Boolean
        get() = p.getBoolean("stats", true)
        set(v) = p.edit().putBoolean("stats", v).apply()
}
