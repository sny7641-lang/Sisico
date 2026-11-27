package com.sisico.remote

import android.app.Activity
import android.app.AlertDialog
import android.app.KeyguardManager
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal
import android.os.SystemClock

/**
 * 앱 잠금: PC에 접속하기 전에 휴대폰 잠금(지문·얼굴·PIN·패턴)으로 본인 확인.
 * 한 번 확인하면 5분 동안은 다시 묻지 않음.
 */
object AppLock {
    private const val REQUEST = 7101
    private const val GRACE_MS = 5 * 60 * 1000L

    private var lastAuth = 0L
    private var inProgress = false
    private var pending: ((Boolean) -> Unit)? = null

    fun enabled(act: Activity) = Settings(act).appLock

    private fun fresh() = lastAuth != 0L && SystemClock.elapsedRealtime() - lastAuth < GRACE_MS

    /**
     * 본인 확인 후 done(true/false). 확인 중에 다시 불리면(확인 화면 때문에 화면이 잠깐 가려졌다 돌아온 경우)
     * 아무것도 하지 않음 — 처음 요청의 결과가 처리함.
     */
    fun require(act: Activity, reason: String, force: Boolean = false, done: (Boolean) -> Unit) {
        if (inProgress) return
        if (!force && (!enabled(act) || fresh())) { done(true); return }
        val km = act.getSystemService(KeyguardManager::class.java)
        if (km == null || !km.isDeviceSecure) {
            AlertDialog.Builder(act).setTitle("앱 잠금")
                .setMessage("휴대폰에 화면 잠금(PIN·패턴·지문)이 설정되어 있지 않아 본인 확인을 할 수 없습니다.\n" +
                    "휴대폰 설정 → 잠금 화면에서 먼저 설정해 주세요.")
                .setPositiveButton("그냥 계속") { _, _ -> done(true) }
                .setNegativeButton("취소") { _, _ -> done(false) }.show()
            return
        }
        inProgress = true
        val finish = { ok: Boolean ->
            inProgress = false
            if (ok) lastAuth = SystemClock.elapsedRealtime()
            done(ok)
        }
        if (Build.VERSION.SDK_INT >= 30) {
            val prompt = BiometricPrompt.Builder(act)
                .setTitle("Sisico 원격")
                .setSubtitle(reason)
                .setAllowedAuthenticators(
                    BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL
                ).build()
            prompt.authenticate(CancellationSignal(), act.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = finish(true)
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) = finish(false)
            })
        } else {
            @Suppress("DEPRECATION")
            val intent = km.createConfirmDeviceCredentialIntent("Sisico 원격", reason)
            if (intent == null) { finish(true); return }
            pending = finish
            act.startActivityForResult(intent, REQUEST)
        }
    }

    /** 액티비티의 onActivityResult 에서 먼저 불러 줌. 처리했으면 true */
    fun onActivityResult(requestCode: Int, resultCode: Int): Boolean {
        if (requestCode != REQUEST) return false
        val p = pending
        pending = null
        p?.invoke(resultCode == Activity.RESULT_OK)
        return true
    }
}
