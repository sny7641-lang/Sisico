package com.sisico.remote

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import android.os.SystemClock

/**
 * 원격 접속할 때만 Tailscale VPN 을 켜고, 끝나면 다시 끔 (평소엔 VPN 이 꺼져 있어 삼성페이 등이 정상 동작).
 * Tailscale 앱이 받는 신호(브로드캐스트)를 씀: com.tailscale.ipn.CONNECT_VPN / DISCONNECT_VPN.
 * 앱이 직접 켠 경우에만 끄고, 사용자가 원래 켜 둔 VPN 은 건드리지 않음.
 */
object TailscaleControl {
    private const val PKG = "com.tailscale.ipn"
    private const val RECEIVER = "com.tailscale.ipn.IPNReceiver"

    /** 우리 앱이 켠 상태인지 (끌 때 확인) */
    @Volatile var startedByUs = false
        private set

    fun installed(ctx: Context): Boolean = try {
        ctx.packageManager.getPackageInfo(PKG, 0); true
    } catch (e: PackageManager.NameNotFoundException) { false }

    fun vpnActive(ctx: Context): Boolean {
        val cm = ctx.getSystemService(ConnectivityManager::class.java) ?: return false
        @Suppress("DEPRECATION")
        return cm.allNetworks.any { cm.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true }
    }

    /** Tailscale 주소(100.64.0.0/10)나 .ts.net 이름이면 Tailscale 이 필요한 PC */
    fun needed(address: String): Boolean {
        val a = address.trim().lowercase()
        if (a.endsWith(".ts.net")) return true
        val parts = a.split(".")
        if (parts.size != 4) return a.startsWith("fd7a:115c:a1e0")
        val p0 = parts[0].toIntOrNull() ?: return false
        val p1 = parts[1].toIntOrNull() ?: return false
        return p0 == 100 && p1 in 64..127
    }

    private fun send(ctx: Context, vararg actions: String) {
        for (a in actions) {
            try {
                ctx.sendBroadcast(Intent(a).setClassName(PKG, RECEIVER))
            } catch (_: Exception) {}
        }
    }

    /**
     * 필요하면 Tailscale 을 켜고 VPN 이 실제로 연결될 때까지(최대 15초) 기다린 뒤 onReady(켜짐 여부) 호출.
     * 설정에서 끈 경우·Tailscale 미설치·이미 켜져 있음 → 바로 onReady.
     */
    fun ensureOn(ctx: Context, address: String, onReady: (Boolean) -> Unit) {
        val app = ctx.applicationContext
        if (!Settings(app).autoTailscale || !needed(address) || !installed(app) || vpnActive(app)) {
            onReady(vpnActive(app)); return
        }
        send(app, "$PKG.CONNECT_VPN", "$PKG.VPN_CONNECT")   // 버전에 따라 이름이 달라 둘 다 보냄
        startedByUs = true
        val ui = Handler(Looper.getMainLooper())
        val until = SystemClock.uptimeMillis() + 15_000
        ui.post(object : Runnable {
            override fun run() {
                if (vpnActive(app)) {
                    ui.postDelayed({ onReady(true) }, 700)   // 경로가 잡히도록 잠깐 더 기다림
                } else if (SystemClock.uptimeMillis() > until) {
                    onReady(false)
                } else ui.postDelayed(this, 300)
            }
        })
    }

    /** 우리가 켠 경우에만 끔 */
    fun offIfWeStarted(ctx: Context) {
        if (!startedByUs) return
        startedByUs = false
        send(ctx.applicationContext, "$PKG.DISCONNECT_VPN", "$PKG.VPN_DISCONNECT")
    }
}
