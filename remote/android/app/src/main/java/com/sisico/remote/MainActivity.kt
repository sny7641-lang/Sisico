package com.sisico.remote

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.util.UUID

/** 저장한 PC 목록. 누르면 연결, 길게 누르면 수정·삭제. */
class MainActivity : Activity() {

    private lateinit var list: LinearLayout
    private lateinit var lockButton: Button
    private lateinit var tsButton: Button

    private fun updateTsButton() {
        tsButton.text = if (Settings(this).autoTailscale) "🛡 Tailscale 자동: 접속할 때만 켜고 끝나면 끔" else "🛡 Tailscale 자동: 꺼짐 (직접 켜고 끄기)"
    }

    private fun toggleTs() {
        val s = Settings(this)
        s.autoTailscale = !s.autoTailscale
        updateTsButton()
        if (s.autoTailscale && !TailscaleControl.installed(this)) {
            AlertDialog.Builder(this).setMessage("Tailscale 앱이 설치되어 있지 않습니다. Play 스토어에서 설치하고 로그인해 두세요.")
                .setPositiveButton("확인", null).show()
        } else if (s.autoTailscale) {
            AlertDialog.Builder(this).setTitle("Tailscale 자동")
                .setMessage("100.x.x.x 주소로 등록한 PC에 접속할 때만 Tailscale 을 켜고, 원격을 끝내거나 다른 앱으로 가면 끕니다.\n\n" +
                    "Tailscale 앱 설정에서 '항상 켜짐(Always-on VPN)'은 꺼 두세요.")
                .setPositiveButton("확인", null).show()
        }
    }
    private fun updateLockButton() {
        lockButton.text = if (Settings(this).appLock) "🔒 앱 잠금: 켜짐 (접속할 때 지문·PIN 확인)" else "🔓 앱 잠금: 꺼짐"
    }

    private fun toggleLock() {
        val s = Settings(this)
        if (s.appLock) {   // 끄는 것도 본인 확인 후에만
            AppLock.require(this, "앱 잠금을 끄려면 본인 확인이 필요합니다", force = true) { ok ->
                if (ok) { s.appLock = false; updateLockButton() }
            }
        } else {
            s.appLock = true; updateLockButton()
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (AppLock.onActivityResult(requestCode, resultCode)) return
        super.onActivityResult(requestCode, resultCode, data)
    }
    private fun dp(v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        root.addView(TextView(this).apply {
            text = "Sisico 원격"; textSize = 22f; setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.WHITE); setBackgroundColor(0xFF0F6B66.toInt())
            setPadding(dp(20), dp(18), dp(20), dp(18))
        })

        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(12), dp(12), dp(12), dp(12)) }
        root.addView(ScrollView(this).apply { addView(list) }, LinearLayout.LayoutParams(-1, 0, 1f))

        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; setPadding(dp(12), dp(4), dp(12), dp(16))
        }
        buttons.addView(Button(this).apply {
            text = "+ PC 추가"; setOnClickListener { editHost(null) }
        }, LinearLayout.LayoutParams(0, -2, 1f))
        buttons.addView(Button(this).apply {
            text = "와이파이에서 찾기"; setOnClickListener { discover() }
        }, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(buttons)
        tsButton = Button(this).apply { setOnClickListener { toggleTs() } }
        root.addView(tsButton, LinearLayout.LayoutParams(-1, -2).apply { setMargins(dp(12), 0, dp(12), 0) })
        updateTsButton()
        lockButton = Button(this).apply { setOnClickListener { toggleLock() } }
        root.addView(lockButton, LinearLayout.LayoutParams(-1, -2).apply { setMargins(dp(12), 0, dp(12), dp(12)) })
        updateLockButton()
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        refresh()
    }

    private fun refresh() {
        list.removeAllViews()
        val hosts = HostStore.load(this)
        if (hosts.isEmpty()) {
            list.addView(TextView(this).apply {
                textSize = 14f; setTextColor(0xFF555555.toInt()); setLineSpacing(0f, 1.3f)
                text = "등록된 PC가 없습니다.\n\n" +
                    "1. 윈도우 PC에서 sisico_remote_host.exe 를 실행하고 비밀번호를 정합니다.\n" +
                    "2. 같은 와이파이라면 '와이파이에서 찾기', 아니면 '+ PC 추가' 에 PC 주소를 넣습니다.\n" +
                    "3. 밖에서 쓰려면 PC와 휴대폰에 Tailscale 을 깔고 100.x.x.x 주소를 넣으세요."
            })
            return
        }
        for (h in hosts) {
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                background = GradientDrawable().apply { setColor(Color.WHITE); cornerRadius = dp(12).toFloat() }
                setPadding(dp(16), dp(14), dp(16), dp(14))
                elevation = dp(2).toFloat()
                isClickable = true
                setOnClickListener {
                    if (h.needsPairing) {
                        AlertDialog.Builder(this@MainActivity).setTitle("다시 등록이 필요합니다")
                            .setMessage("보안이 강화되어(암호화 연결) 이 PC를 한 번 다시 등록해야 합니다.\nPC 프로그램도 최신 버전으로 바꿔 주세요.")
                            .setPositiveButton("다시 등록") { _, _ -> editHost(h) }.setNegativeButton("취소", null).show()
                    } else AppLock.require(this@MainActivity, "PC에 접속하려면 본인 확인이 필요합니다") { ok ->
                        if (ok) startActivity(Intent(this@MainActivity, RemoteActivity::class.java).putExtra("id", h.id))
                    }
                }
                setOnLongClickListener { hostMenu(h); true }
            }
            card.addView(TextView(this).apply {
                text = "🖥  " + h.name.ifEmpty { h.address }; textSize = 17f; setTextColor(0xFF1A1A1A.toInt())
            })
            card.addView(TextView(this).apply {
                text = "${h.address}:${h.port}"; textSize = 13f; setTextColor(0xFF777777.toInt())
            })
            list.addView(card, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(10) })
        }
        list.addView(TextView(this).apply {
            text = "길게 누르면 수정·삭제"; textSize = 12f; setTextColor(0xFF999999.toInt()); gravity = Gravity.CENTER
        })
    }

    private fun hostMenu(h: HostEntry) {
        AlertDialog.Builder(this).setTitle(h.name.ifEmpty { h.address })
            .setItems(arrayOf("수정", "삭제")) { _, i ->
                if (i == 0) editHost(h)
                else AlertDialog.Builder(this).setMessage("삭제할까요?")
                    .setPositiveButton("삭제") { _, _ ->
                        HostStore.save(this, HostStore.load(this).filter { it.id != h.id }); refresh()
                    }.setNegativeButton("취소", null).show()
            }.show()
    }

    private fun editHost(old: HostEntry?, preset: Triple<String, String, Int>? = null) {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(8), dp(20), 0) }
        fun field(hint: String, value: String, type: Int) = EditText(this).apply {
            this.hint = hint; setText(value); inputType = type; box.addView(this)
        }
        val name = field("이름 (예: 집 PC)", old?.name ?: preset?.first ?: "", InputType.TYPE_CLASS_TEXT)
        val addr = field("주소 (예: 192.168.0.10)", old?.address ?: preset?.second ?: "", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        val port = field("포트", (old?.port ?: preset?.third ?: 8765).toString(), InputType.TYPE_CLASS_NUMBER)
        val pw = field(if (old != null && !old.needsPairing) "비밀번호 (바꿀 때만 입력)" else "PC에서 정한 비밀번호",
            "", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD)

        val dlg = AlertDialog.Builder(this).setTitle(if (old == null) "PC 추가" else "PC 수정")
            .setView(box).setPositiveButton("저장", null).setNegativeButton("취소", null).create()
        dlg.setOnShowListener {
            dlg.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val a = addr.text.toString().trim()
                val p = port.text.toString().toIntOrNull() ?: 8765
                val password = pw.text.toString()
                if (a.isEmpty()) { addr.error = "주소를 입력하세요"; return@setOnClickListener }
                val base = HostEntry(old?.id ?: UUID.randomUUID().toString(), name.text.toString().trim(), a, p,
                    old?.keyHex ?: "", old?.pin ?: "")
                if (password.isEmpty()) {
                    if (old == null || old.needsPairing) { pw.error = "비밀번호를 입력하세요"; return@setOnClickListener }
                    saveHost(base); dlg.dismiss()   // 이름·주소만 바꿈 (지문은 접속할 때마다 확인)
                } else {
                    dlg.dismiss()
                    pair(base, password)
                }
            }
        }
        dlg.show()
    }

    private fun saveHost(entry: HostEntry) {
        val all = HostStore.load(this)
        val idx = all.indexOfFirst { it.id == entry.id }
        if (idx >= 0) all[idx] = entry else all.add(entry)
        HostStore.save(this, all)
        refresh()
    }

    /**
     * PC 등록: 암호화 연결 → PC 인증서 지문을 사용자에게 확인 → 비밀번호로 만든 키로 로그인 시험 → 저장.
     * 지문을 확인하기 전에는 비밀번호에서 나온 키를 보내지 않습니다.
     */
    private fun pair(base: HostEntry, password: String) {
        val wait = AlertDialog.Builder(this).setMessage("${base.address} 에 연결 중…").setCancelable(false).show()
        TailscaleControl.ensureOn(this, base.address) { pairConnect(base, password, wait) }
    }

    private fun pairConnect(base: HostEntry, password: String, wait: AlertDialog) {
        var client: RemoteClient? = null
        var pin = ""
        var key = ""
        client = RemoteClient(base, object : RemoteClient.Callback {
            override fun onPairHello(fingerprint: String, salt: String, iterations: Int, pcName: String) = runOnUiThread {
                pin = fingerprint
                val proceed = {
                    wait.setMessage("비밀번호 확인 중…")
                    Thread {
                        key = HostStore.deriveKey(password, salt, iterations)
                        client?.sendAuth(key)
                    }.start()
                }
                if (base.pin == fingerprint) { proceed(); return@runOnUiThread }   // 이미 확인한 PC
                wait.hide()
                AlertDialog.Builder(this@MainActivity).setTitle("이 PC가 맞나요?")
                    .setMessage("PC 이름: $pcName\n\nPC의 Sisico 원격 창에 나온 지문과 같은지 확인하세요.\n\n" +
                        "      ${HostStore.shortFp(fingerprint)}\n\n" +
                        (if (base.pin.isNotEmpty()) "⚠ 전에 등록한 지문과 다릅니다. PC 프로그램을 새로 설치한 게 아니라면 '아니요'를 누르세요.\n\n" else "") +
                        "다르면 다른 기기가 PC인 척하는 것일 수 있습니다.")
                    .setCancelable(false)
                    .setPositiveButton("같아요") { _, _ -> wait.show(); proceed() }
                    .setNegativeButton("아니요") { _, _ -> client?.close(); wait.dismiss() }
                    .show()
            }.let {}

            override fun onAuthed(pcName: String, monitors: List<Monitor>) = runOnUiThread {
                client?.close()
                TailscaleControl.offIfWeStarted(this@MainActivity)
                wait.dismiss()
                saveHost(base.copy(name = base.name.ifEmpty { pcName }, keyHex = key, pin = pin))
                Toast.makeText(this@MainActivity, "등록했습니다", Toast.LENGTH_SHORT).show()
            }.let {}

            override fun onClosed(reason: String, authFailed: Boolean) = runOnUiThread {
                TailscaleControl.offIfWeStarted(this@MainActivity)
                wait.dismiss()
                AlertDialog.Builder(this@MainActivity).setTitle("등록하지 못했습니다").setMessage(reason)
                    .setPositiveButton("다시 입력") { _, _ -> editHost(base) }
                    .setNegativeButton("닫기", null).show()
            }.let {}
        }, pairing = true)
        client!!.connect()
    }

    /** 같은 네트워크에 브로드캐스트를 보내 실행 중인 호스트를 찾습니다. */
    private fun discover() {
        val wait = AlertDialog.Builder(this).setMessage("같은 와이파이에서 PC를 찾는 중…").setCancelable(false).show()
        Thread {
            val found = LinkedHashMap<String, Triple<String, String, Int>>()
            try {
                DatagramSocket().use { sock ->
                    sock.broadcast = true
                    sock.soTimeout = 400
                    val msg = "SISICO_REMOTE_DISCOVER".toByteArray()
                    val end = System.currentTimeMillis() + 2000
                    var nextSend = 0L
                    val buf = ByteArray(1024)
                    while (System.currentTimeMillis() < end) {
                        if (System.currentTimeMillis() >= nextSend) {
                            sock.send(DatagramPacket(msg, msg.size, InetAddress.getByName("255.255.255.255"), 8766))
                            nextSend = System.currentTimeMillis() + 600
                        }
                        try {
                            val pkt = DatagramPacket(buf, buf.size)
                            sock.receive(pkt)
                            val o = JSONObject(String(pkt.data, 0, pkt.length))
                            val ip = pkt.address.hostAddress ?: continue
                            found[ip] = Triple(o.optString("name"), ip, o.optInt("port", 8765))
                        } catch (_: SocketTimeoutException) {
                        } catch (_: Exception) {}
                    }
                }
            } catch (_: Exception) {}
            runOnUiThread {
                wait.dismiss()
                if (found.isEmpty()) {
                    AlertDialog.Builder(this).setTitle("찾지 못했습니다")
                        .setMessage("PC에서 호스트가 실행 중인지, 같은 와이파이인지, 윈도우 방화벽에서 '개인 네트워크' 허용을 눌렀는지 확인하세요.\n\n'+ PC 추가'로 주소를 직접 넣어도 됩니다.")
                        .setPositiveButton("확인", null).show()
                } else {
                    val items = found.values.toList()
                    AlertDialog.Builder(this).setTitle("찾은 PC")
                        .setItems(items.map { "${it.first}  (${it.second})" }.toTypedArray()) { _, i -> editHost(null, items[i]) }
                        .show()
                }
            }
        }.start()
    }

    @Suppress("unused")
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
