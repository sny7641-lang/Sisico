package com.sisico.remote

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.util.TypedValue
import android.view.Gravity
import android.view.KeyEvent
import android.view.Surface
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject

class RemoteActivity : Activity(), RemoteClient.Callback, ScreenView.Listener {

    private lateinit var host: HostEntry
    private lateinit var settings: Settings
    private lateinit var screen: ScreenView
    private lateinit var stats: TextView
    private lateinit var status: LinearLayout
    private lateinit var statusText: TextView
    private lateinit var bottom: LinearLayout
    private lateinit var toolbar: View
    private lateinit var keyPanel: LinearLayout
    private lateinit var input: EditText
    private lateinit var modeButton: Button

    private val ui = Handler(Looper.getMainLooper())
    private var client: RemoteClient? = null
    private var monitors: List<Monitor> = emptyList()
    private var currentMon = 0

    @Volatile private var surface: Surface? = null
    @Volatile private var decoder: H264Decoder? = null
    @Volatile private var streamCodec = ""
    private var streamW = 0
    private var streamH = 0

    // 통계
    @Volatile private var bytesIn = 0L
    @Volatile private var jpegFrames = 0L
    private var lastFrames = 0L
    private var rtt = -1L
    private var closedByUser = false

    private val files = FileTransfer(this) { client }

    private val mods = linkedSetOf<Int>()
    private val modButtons = HashMap<Int, Button>()

    private fun dp(v: Int) = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), resources.displayMetrics).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val h = HostStore.get(this, intent.getStringExtra("id") ?: "")
        if (h == null) { finish(); return }
        host = h
        settings = Settings(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        buildUi()
        hideSystemBars()
        connect()
        ui.post(tick)
    }

    // ================================================================ 화면 구성
    private fun buildUi() {
        val root = FrameLayout(this)
        screen = ScreenView(this, this).apply {
            trackpad = settings.trackpad
            speed = settings.speed
        }
        root.addView(screen, FrameLayout.LayoutParams(-1, -1))

        stats = TextView(this).apply {
            setTextColor(Color.WHITE); textSize = 11f
            setBackgroundColor(0x66000000); setPadding(dp(6), dp(2), dp(6), dp(2))
            visibility = if (settings.showStats) View.VISIBLE else View.GONE
        }
        root.addView(stats, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START))

        // 연결 중 표시
        status = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            addView(ProgressBar(this@RemoteActivity))
            statusText = TextView(this@RemoteActivity).apply {
                setTextColor(Color.WHITE); textSize = 15f; gravity = Gravity.CENTER
                setPadding(dp(16), dp(12), dp(16), 0)
            }
            addView(statusText)
        }
        root.addView(status, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))

        // 메뉴 열기 버튼 (오른쪽 위)
        val fab = Button(this).apply {
            text = "☰"; textSize = 18f; setTextColor(Color.WHITE)
            background = round(0x99000000.toInt(), dp(22))
            setOnClickListener { toggleToolbar() }
        }
        root.addView(fab, FrameLayout.LayoutParams(dp(44), dp(44), Gravity.TOP or Gravity.END).apply {
            setMargins(0, dp(8), dp(8), 0)
        })

        bottom = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        keyPanel = buildKeyPanel().apply { visibility = View.GONE }
        bottom.addView(keyPanel)
        toolbar = buildToolbar()
        bottom.addView(toolbar)
        root.addView(bottom, FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM))

        setContentView(root)
    }

    private fun round(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = radius.toFloat() }

    private fun barButton(label: String, onClick: (Button) -> Unit) = Button(this).apply {
        text = label; textSize = 13f; isAllCaps = false; setTextColor(Color.WHITE)
        background = round(0x33FFFFFF, dp(8))
        minWidth = 0; minimumWidth = 0; minHeight = 0; minimumHeight = 0
        setPadding(dp(12), dp(8), dp(12), dp(8))
        setOnClickListener { onClick(this) }
        layoutParams = LinearLayout.LayoutParams(-2, -2).apply { setMargins(dp(3), dp(4), dp(3), dp(4)) }
    }

    private fun scrollRow(vararg views: View): HorizontalScrollView {
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(dp(4), 0, dp(4), 0) }
        views.forEach { row.addView(it) }
        return HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(row) }
    }

    private fun buildToolbar(): View {
        modeButton = barButton(modeLabel()) { toggleMode() }
        return scrollRow(
            barButton("⌨ 키보드") { toggleKeyboard() },
            modeButton,
            barButton("⌘ 단축키") { showShortcuts() },
            barButton("🖥 모니터") { showMonitors() },
            barButton("⚙ 화질") { showSettings() },
            barButton("📁 파일") { files.showMenu() },
            barButton("📋 클립보드") { showClipboard() },
            barButton("⤢ 원래 크기") { screen.resetZoom() },
            barButton("✕ 끊기") { confirmExit() },
        ).apply { setBackgroundColor(0xCC101418.toInt()) }
    }

    private fun modeLabel() = if (settings.trackpad) "🖱 트랙패드" else "👆 터치"

    private fun buildKeyPanel(): LinearLayout {
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; setBackgroundColor(0xE6101418.toInt())
        }
        input = EditText(this).apply {
            hint = "여기에 입력하면 PC로 바로 들어갑니다"
            setHintTextColor(0x88FFFFFF.toInt()); setTextColor(Color.WHITE); textSize = 15f
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            imeOptions = EditorInfo.IME_ACTION_SEND or EditorInfo.IME_FLAG_NO_EXTRACT_UI or EditorInfo.IME_FLAG_NO_FULLSCREEN
            isSingleLine = true
            background = round(0x22FFFFFF, dp(6)); setPadding(dp(10), dp(8), dp(10), dp(8))
            setOnEditorActionListener { _, _, _ -> flushInput(); sendKey(VK.ENTER); true }
            setOnKeyListener { _, code, ev ->
                if (ev.action == KeyEvent.ACTION_DOWN && code == KeyEvent.KEYCODE_DEL && text.isEmpty()) {
                    sendKey(VK.BACK); true
                } else false
            }
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun afterTextChanged(s: Editable) {
                    // 한글 조합 중이 아니면 바로 보냄 (조합 중인 글자는 완성된 뒤 보냄)
                    if (s.isNotEmpty() && BaseInputConnection.getComposingSpanStart(s) == -1) ui.post { flushInput() }
                }
            })
        }
        val send = barButton("보내기") { flushInput() }
        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(6), dp(6), dp(6), 0)
            addView(input, LinearLayout.LayoutParams(0, -2, 1f))
            addView(send)
        }
        panel.addView(top)

        val keys = ArrayList<View>()
        for ((label, vk) in listOf("Ctrl" to VK.CTRL, "Alt" to VK.ALT, "Shift" to VK.SHIFT, "Win" to VK.WIN)) {
            keys += barButton(label) { toggleMod(vk) }.also { modButtons[vk] = it }
        }
        val plain = listOf(
            "Esc" to VK.ESC, "Tab" to VK.TAB, "⌫" to VK.BACK, "Enter" to VK.ENTER, "Del" to VK.DEL,
            "←" to VK.LEFT, "↑" to VK.UP, "↓" to VK.DOWN, "→" to VK.RIGHT,
            "Home" to VK.HOME, "End" to VK.END, "PgUp" to VK.PGUP, "PgDn" to VK.PGDN,
            "한/영" to VK.HANGUL, "한자" to VK.HANJA, "Space" to VK.SPACE, "PrtSc" to VK.PRTSC,
        ) + (1..12).map { "F$it" to VK.F1 + it - 1 }
        for ((label, vk) in plain) keys += barButton(label) { sendKey(vk) }
        panel.addView(scrollRow(*keys.toTypedArray()))
        return panel
    }

    private fun hideSystemBars() {
        if (Build.VERSION.SDK_INT >= 30) {
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_STABLE)
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    // ================================================================ 연결
    private fun connect() {
        closedByUser = false
        showStatus("${host.name.ifEmpty { host.address }} 에 연결 중…")
        client = RemoteClient(host, this).also { it.connect() }
    }

    private fun disconnect() {
        closedByUser = true
        client?.close()
        client = null
        decoder?.release()
        decoder = null
        streamCodec = ""
    }

    private fun showStatus(msg: String?) {
        status.visibility = if (msg == null) View.GONE else View.VISIBLE
        statusText.text = msg ?: ""
    }

    private fun startMessage(type: String) = client?.msg(
        type, "codec" to settings.codec, "mon" to currentMon, "fps" to settings.fps,
        "maxw" to settings.maxSide, "kbps" to settings.kbps, "q" to settings.jpegQuality,
    )

    override fun onAuthed(pcName: String, monitors: List<Monitor>) = ui.post {
        this.monitors = monitors
        if (currentMon >= monitors.size) currentMon = 0
        showStatus("화면 받는 중…")
        startMessage("start")
    }.let {}

    override fun onStream(codec: String, w: Int, h: Int, monW: Int, monH: Int) = ui.post {
        showStatus(null)
        streamW = w; streamH = h
        screen.setFrameSize(w, h, monW, monH)
        decoder?.release(); decoder = null
        streamCodec = codec
        startDecoderIfReady()
    }.let {}

    private fun startDecoderIfReady() {
        val s = surface ?: return
        if (streamCodec == "h264" && decoder == null && streamW > 0) {
            decoder = H264Decoder(s, streamW, streamH) { client?.msg("kf") }
            client?.msg("kf")
        }
    }

    override fun onSurface(surface: Surface?) {
        this.surface = surface
        if (surface == null) { decoder?.release(); decoder = null } else startDecoderIfReady()
    }

    private val jpegPaint = Paint(Paint.FILTER_BITMAP_FLAG)

    override fun onVideo(kind: Int, key: Boolean, data: ByteArray, offset: Int) {
        bytesIn += data.size
        when (kind) {
            1 -> decoder?.offer(data, offset, key)
            3 -> files.onChunk(data, offset)
            2 -> {
                val s = surface ?: return
                val bmp = BitmapFactory.decodeByteArray(data, offset, data.size - offset) ?: return
                try {
                    val c = s.lockCanvas(null)
                    c.drawBitmap(bmp, null, Rect(0, 0, c.width, c.height), jpegPaint)
                    s.unlockCanvasAndPost(c)
                    jpegFrames++
                } catch (_: Exception) {
                } finally { bmp.recycle() }
            }
        }
    }

    override fun onCursor(x: Float, y: Float) = ui.post { screen.setCursor(x, y) }.let {}

    override fun onPong(rttMs: Long) { rtt = rttMs }

    override fun onClipboard(text: String) = ui.post {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("PC", text))
        toast(if (text.isEmpty()) "PC 클립보드가 비어 있습니다" else "PC 클립보드를 복사했습니다 (${text.length}자)")
    }.let {}

    override fun onOther(m: JSONObject) { files.onMessage(m) }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FileTransfer.PICK_REQUEST && resultCode == RESULT_OK) files.onPicked(data)
    }

    override fun onClosed(reason: String, authFailed: Boolean) = ui.post {
        files.abort()
        if (closedByUser || isFinishing) return@post
        decoder?.release(); decoder = null
        streamCodec = ""
        showStatus(reason)
        val b = AlertDialog.Builder(this).setTitle("연결 끊김").setMessage(reason).setCancelable(false)
            .setNegativeButton("닫기") { _, _ -> finish() }
        if (!authFailed) b.setPositiveButton("다시 연결") { _, _ -> connect() }
        b.show()
    }.let {}

    private val tick = object : Runnable {
        var lastBytes = 0L
        override fun run() {
            client?.takeIf { it.authed }?.msg("ping", "ts" to System.currentTimeMillis())
            val frames = (decoder?.renderedFrames ?: 0L) + jpegFrames
            val fps = (frames - lastFrames).coerceAtLeast(0)
            lastFrames = frames
            val kbps = (bytesIn - lastBytes) * 8 / 1000
            lastBytes = bytesIn
            if (streamCodec.isNotEmpty()) {
                stats.text = "${streamCodec.uppercase()} ${streamW}×$streamH · ${fps}fps · ${kbps}kbps" +
                    (if (rtt >= 0) " · ${rtt}ms" else "")
            }
            ui.postDelayed(this, 1000)
        }
    }

    // ================================================================ 입력 보내기 (ScreenView.Listener)
    override fun moveAbs(nx: Float, ny: Float) { client?.msg("mm", "x" to nx.toDouble(), "y" to ny.toDouble()) }
    override fun moveRel(dx: Float, dy: Float) { client?.msg("mr", "dx" to dx.toDouble(), "dy" to dy.toDouble()) }
    override fun button(name: String, down: Boolean) { client?.msg("mb", "b" to name, "d" to down) }
    override fun click(name: String) { client?.msg("click", "b" to name) }
    override fun wheel(dy: Int, dx: Int) { client?.msg("wh", "dy" to dy, "dx" to dx) }

    private fun sendKey(vk: Int) {
        if (mods.isEmpty()) {
            client?.msg("key", "vk" to vk, "d" to true)
            client?.msg("key", "vk" to vk, "d" to false)
        } else {
            combo(mods.toList() + vk)
            clearMods()
        }
    }

    private fun combo(vks: List<Int>) {
        client?.msg("combo", "vks" to JSONArray(vks))
    }

    private fun flushInput() {
        val s = input.text.toString()
        if (s.isEmpty()) return
        input.text.clear()
        if (mods.isNotEmpty() && s.length == 1 && VK.letter(s[0]) != null) {
            combo(mods.toList() + VK.letter(s[0])!!)   // 예: Ctrl 켜고 c 입력 → Ctrl+C
            clearMods()
        } else {
            client?.msg("text", "s" to s)
        }
    }

    private fun toggleMod(vk: Int) {
        if (!mods.remove(vk)) mods.add(vk)
        modButtons[vk]?.background = round(if (vk in mods) 0xFF0F6B66.toInt() else 0x33FFFFFF, dp(8))
    }

    private fun clearMods() {
        mods.clear()
        modButtons.values.forEach { it.background = round(0x33FFFFFF, dp(8)) }
    }

    /** 블루투스/USB 키보드를 연결했을 때: 키를 그대로 PC로 */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val typing = keyPanel.visibility == View.VISIBLE && input.hasFocus()
        val code = event.keyCode
        if (!typing && code != KeyEvent.KEYCODE_BACK && code != KeyEvent.KEYCODE_VOLUME_UP &&
            code != KeyEvent.KEYCODE_VOLUME_DOWN && event.device?.isVirtual == false
        ) {
            val vk = VK.fromAndroid(code)
            if (vk != null && (event.action == KeyEvent.ACTION_DOWN || event.action == KeyEvent.ACTION_UP)) {
                client?.msg("key", "vk" to vk, "d" to (event.action == KeyEvent.ACTION_DOWN))
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    // ================================================================ 메뉴
    private fun toggleToolbar() {
        val show = bottom.visibility != View.VISIBLE
        bottom.visibility = if (show) View.VISIBLE else View.GONE
        if (!show) hideKeyboard()
    }

    private fun toggleKeyboard() {
        if (keyPanel.visibility == View.VISIBLE) {
            hideKeyboard()
        } else {
            keyPanel.visibility = View.VISIBLE
            input.requestFocus()
            (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input, 0)
        }
    }

    private fun hideKeyboard() {
        flushInput()
        keyPanel.visibility = View.GONE
        (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(input.windowToken, 0)
        input.clearFocus()
        hideSystemBars()
    }

    private fun toggleMode() {
        settings.trackpad = !settings.trackpad
        screen.trackpad = settings.trackpad
        modeButton.text = modeLabel()
        toast(if (settings.trackpad) "트랙패드 모드: 노트북 터치패드처럼 조작" else "터치 모드: 누른 곳을 바로 클릭")
    }

    private fun showShortcuts() {
        val items = listOf(
            "Alt + Tab (창 전환)" to listOf(VK.ALT, VK.TAB),
            "Win (시작 메뉴)" to listOf(VK.WIN),
            "Win + D (바탕 화면)" to listOf(VK.WIN, 'D'.code),
            "Win + E (탐색기)" to listOf(VK.WIN, 'E'.code),
            "Win + R (실행)" to listOf(VK.WIN, 'R'.code),
            "Ctrl + Shift + Esc (작업 관리자)" to listOf(VK.CTRL, VK.SHIFT, VK.ESC),
            "Alt + F4 (창 닫기)" to listOf(VK.ALT, VK.F1 + 3),
            "Ctrl + C (복사)" to listOf(VK.CTRL, 'C'.code),
            "Ctrl + V (붙여넣기)" to listOf(VK.CTRL, 'V'.code),
            "Ctrl + X (잘라내기)" to listOf(VK.CTRL, 'X'.code),
            "Ctrl + Z (실행 취소)" to listOf(VK.CTRL, 'Z'.code),
            "Ctrl + A (모두 선택)" to listOf(VK.CTRL, 'A'.code),
            "Ctrl + S (저장)" to listOf(VK.CTRL, 'S'.code),
            "Win + Shift + S (화면 캡처)" to listOf(VK.WIN, VK.SHIFT, 'S'.code),
            "볼륨 크게" to listOf(VK.VOL_UP),
            "볼륨 작게" to listOf(VK.VOL_DOWN),
            "음소거" to listOf(VK.VOL_MUTE),
            "재생 / 일시정지" to listOf(VK.MEDIA_PLAY),
            "가운데 버튼 클릭" to emptyList(),
        )
        AlertDialog.Builder(this).setTitle("단축키")
            .setItems(items.map { it.first }.toTypedArray()) { _, i ->
                val vks = items[i].second
                if (vks.isEmpty()) click("middle") else combo(vks)
            }.show()
    }

    private fun showMonitors() {
        if (monitors.isEmpty()) return
        val names = monitors.mapIndexed { i, m -> "모니터 ${i + 1}  (${m.width}×${m.height})" + if (i == currentMon) "  ✓" else "" }
        AlertDialog.Builder(this).setTitle("모니터 선택").setItems(names.toTypedArray()) { _, i ->
            currentMon = i
            screen.resetZoom()
            startMessage("cfg")
        }.show()
    }

    private fun showSettings() {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(8), dp(20), 0) }
        val oldCodec = settings.codec
        fun group(title: String, opts: List<Pair<String, Any>>, cur: Any, pick: (Any) -> Unit) {
            box.addView(TextView(this).apply { text = title; textSize = 13f; setPadding(0, dp(12), 0, dp(2)) })
            val rg = RadioGroup(this).apply { orientation = RadioGroup.HORIZONTAL }
            opts.forEachIndexed { i, (label, v) ->
                rg.addView(RadioButton(this).apply {
                    id = View.generateViewId(); text = label; textSize = 13f; isChecked = v == cur
                    setOnCheckedChangeListener { _, on -> if (on) pick(opts[i].second) }
                })
            }
            box.addView(HorizontalScrollView(this).apply { addView(rg) })
        }
        group("영상 방식", listOf("H.264 (권장)" to "h264", "JPEG (호환)" to "jpeg"), settings.codec) { settings.codec = it as String }
        group("해상도 (긴 쪽)", listOf("720" to 1280, "1080" to 1920, "1440" to 2560, "원본" to 0), settings.maxSide) { settings.maxSide = it as Int }
        group("초당 프레임", listOf("15" to 15, "30" to 30, "60" to 60), settings.fps) { settings.fps = it as Int }
        group("H.264 비트레이트", listOf("2M" to 2000, "4M" to 4000, "6M" to 6000, "10M" to 10000, "16M" to 16000), settings.kbps) { settings.kbps = it as Int }
        group("JPEG 화질", listOf("50" to 50, "70" to 70, "85" to 85), settings.jpegQuality) { settings.jpegQuality = it as Int }
        group("트랙패드 속도", listOf("느림" to 0.8f, "보통" to 1.3f, "빠름" to 2.0f, "아주 빠름" to 3.0f), settings.speed) {
            settings.speed = it as Float; screen.speed = it
        }
        group("상태 표시", listOf("보이기" to true, "숨기기" to false), settings.showStats) {
            settings.showStats = it as Boolean
            stats.visibility = if (it) View.VISIBLE else View.GONE
        }
        AlertDialog.Builder(this).setTitle("화질 · 조작")
            .setView(ScrollView(this).apply { addView(box) })
            .setPositiveButton("적용") { _, _ ->
                if (settings.codec != oldCodec) {
                    disconnect(); recreate()          // 영상 방식이 바뀌면 화면을 새로 만듦
                } else startMessage("cfg")
            }.setNegativeButton("닫기", null).show()
    }

    private fun showClipboard() {
        AlertDialog.Builder(this).setTitle("클립보드")
            .setItems(arrayOf("휴대폰 → PC 로 보내기", "PC → 휴대폰 으로 가져오기")) { _, i ->
                if (i == 0) {
                    val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    val t = cm.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
                    if (t.isNullOrEmpty()) toast("휴대폰 클립보드가 비어 있습니다")
                    else { client?.msg("clip_set", "s" to t); toast("PC 클립보드에 넣었습니다 (Ctrl+V 로 붙여넣기)") }
                } else client?.msg("clip_get")
            }.show()
    }

    private fun confirmExit() {
        AlertDialog.Builder(this).setMessage("연결을 끊을까요?")
            .setPositiveButton("끊기") { _, _ -> finish() }
            .setNegativeButton("취소", null).show()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (keyPanel.visibility == View.VISIBLE) hideKeyboard() else confirmExit()
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    // ================================================================ 생명주기
    /** 파일 선택 화면에 다녀오는 동안에는 연결을 유지 */
    private var pickingFile = false

    override fun startActivityForResult(intent: Intent?, requestCode: Int, options: Bundle?) {
        if (requestCode == FileTransfer.PICK_REQUEST) pickingFile = true
        super.startActivityForResult(intent, requestCode, options)
    }

    override fun onStop() {
        super.onStop()
        if (!isChangingConfigurations && !pickingFile) disconnect()   // 앱을 내리면 연결을 끊음 (배터리·데이터 절약)
    }

    override fun onRestart() {
        super.onRestart()
        if (pickingFile) { pickingFile = false; client?.msg("kf") } else connect()
    }

    override fun onDestroy() {
        super.onDestroy()
        ui.removeCallbacksAndMessages(null)
        disconnect()
    }
}
