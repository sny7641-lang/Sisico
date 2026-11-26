package com.sisico.remote

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest

/** 저장된 PC 한 대. 비밀번호 대신 sha256(비밀번호) 만 저장합니다. */
data class HostEntry(
    val id: String,
    val name: String,
    val address: String,
    val port: Int,
    val keyHex: String,
) {
    fun toJson() = JSONObject()
        .put("id", id).put("name", name).put("address", address).put("port", port).put("key", keyHex)

    companion object {
        fun fromJson(o: JSONObject) = HostEntry(
            o.getString("id"), o.optString("name"), o.getString("address"),
            o.optInt("port", 8765), o.getString("key"),
        )
    }
}

object HostStore {
    private const val PREFS = "hosts"

    fun passwordKey(pw: String): String =
        MessageDigest.getInstance("SHA-256").digest(pw.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

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
