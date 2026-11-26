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
                setOnClickListener { startActivity(Intent(this@MainActivity, RemoteActivity::class.java).putExtra("id", h.id)) }
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
        val pw = field(if (old != null) "비밀번호 (바꿀 때만 입력)" else "PC에서 정한 비밀번호",
            "", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD)

        val dlg = AlertDialog.Builder(this).setTitle(if (old == null) "PC 추가" else "PC 수정")
            .setView(box).setPositiveButton("저장", null).setNegativeButton("취소", null).create()
        dlg.setOnShowListener {
            dlg.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val a = addr.text.toString().trim()
                val p = port.text.toString().toIntOrNull() ?: 8765
                val password = pw.text.toString()
                if (a.isEmpty()) { addr.error = "주소를 입력하세요"; return@setOnClickListener }
                if (old == null && password.isEmpty()) { pw.error = "비밀번호를 입력하세요"; return@setOnClickListener }
                val key = if (password.isEmpty()) old!!.keyHex else HostStore.passwordKey(password)
                val entry = HostEntry(old?.id ?: UUID.randomUUID().toString(), name.text.toString().trim(), a, p, key)
                val all = HostStore.load(this)
                val idx = all.indexOfFirst { it.id == entry.id }
                if (idx >= 0) all[idx] = entry else all.add(entry)
                HostStore.save(this, all)
                dlg.dismiss(); refresh()
            }
        }
        dlg.show()
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
