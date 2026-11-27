package com.sisico.remote

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.Path
import android.graphics.SurfaceTexture
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.Surface
import android.view.TextureView
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/**
 * PC 화면을 보여주고 터치를 마우스 동작으로 바꿉니다.
 *
 * 트랙패드 모드: 한 손가락 이동 = 커서 이동, 탭 = 왼쪽 클릭, 두 번 탭 후 끌기 / 길게 누른 뒤 끌기 = 드래그,
 *               두 손가락 탭 = 오른쪽 클릭, 두 손가락 끌기 = 스크롤, 벌리기/오므리기 = 확대·축소
 * 터치 모드:     누른 곳을 바로 클릭, 길게 누르기 = 오른쪽 클릭, 끌기 = 드래그 (두 손가락은 같음)
 */
@SuppressLint("ViewConstructor")
class ScreenView(ctx: Context, private val listener: Listener) : FrameLayout(ctx), TextureView.SurfaceTextureListener {

    interface Listener {
        fun onSurface(surface: Surface?)
        fun moveAbs(nx: Float, ny: Float)
        fun moveRel(dx: Float, dy: Float)
        fun button(name: String, down: Boolean)
        fun click(name: String)
        fun wheel(dy: Int, dx: Int)
    }

    val texture = TextureView(ctx)
    var trackpad = true
    var speed = 1.3f
    var accel = 1        // 가속: 0 약, 1 보통, 2 강

    // 원격 화면 크기 (영상 픽셀) 와 PC 모니터 실제 크기
    private var frameW = 0
    private var frameH = 0
    private var monW = 0
    private var monH = 0

    // 표시 상태: 화면에 그려지는 영상의 사각형 = (left, top, dispW*zoom, dispH*zoom)
    private var zoom = 1f
    private var panX = 0f
    private var panY = 0f

    private var cursorX = -1f   // 0~1
    private var cursorY = -1f

    private val slop = ViewConfiguration.get(ctx).scaledTouchSlop.toFloat()
    private val handler = Handler(Looper.getMainLooper())
    private val density = resources.displayMetrics.density

    init {
        texture.surfaceTextureListener = this
        addView(texture, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))
        setWillNotDraw(false)
        setBackgroundColor(Color.BLACK)
    }

    // ------------------------------------------------------------ Surface
    private var surface: Surface? = null

    override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) {
        if (frameW > 0) st.setDefaultBufferSize(frameW, frameH)
        surface = Surface(st)
        listener.onSurface(surface)
    }

    override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) = applyTransform()
    override fun onSurfaceTextureUpdated(st: SurfaceTexture) {}
    override fun onSurfaceTextureDestroyed(st: SurfaceTexture): Boolean {
        listener.onSurface(null)
        surface?.release()
        surface = null
        return true
    }

    fun setFrameSize(w: Int, h: Int, mw: Int, mh: Int) {
        frameW = w; frameH = h
        monW = if (mw > 0) mw else w
        monH = if (mh > 0) mh else h
        texture.surfaceTexture?.setDefaultBufferSize(w, h)
        applyTransform()
    }

    fun setCursor(x: Float, y: Float) {
        // 트랙패드로 막 움직이는 중이면 휴대폰이 그린 커서가 기준 (PC 위치는 한 박자 늦게 오므로 무시)
        if (trackpad && SystemClock.uptimeMillis() - lastLocalMove < 500) return
        cursorX = x; cursorY = y
        if (trackpad && zoom > 1.01f) followCursor()
        invalidate()
    }

    fun resetZoom() {
        zoom = 1f; panX = 0f; panY = 0f
        applyTransform()
    }

    // ------------------------------------------------------------ 좌표 계산
    private fun fitScale(): Float =
        if (frameW == 0 || width == 0) 1f else min(width.toFloat() / frameW, height.toFloat() / frameH)

    private fun dispW() = frameW * fitScale() * zoom
    private fun dispH() = frameH * fitScale() * zoom
    private fun left() = width / 2f + panX - dispW() / 2f
    private fun top() = height / 2f + panY - dispH() / 2f

    private fun clampPan() {
        // 확대했을 때 영상 밖 검은 부분이 필요 이상 보이지 않게
        if (frameW == 0) return
        val maxX = max(0f, (dispW() - width) / 2f)
        val maxY = max(0f, (dispH() - height) / 2f)
        panX = panX.coerceIn(-maxX, maxX)
        panY = panY.coerceIn(-maxY, maxY)
    }

    private fun applyTransform() {
        if (width == 0 || frameW == 0) return
        clampPan()
        val m = Matrix()
        m.setScale(dispW() / width, dispH() / height)
        m.postTranslate(left(), top())
        texture.setTransform(m)
        texture.invalidate()
        invalidate()
    }

    private fun toNorm(x: Float, y: Float) =
        ((x - left()) / dispW()).coerceIn(0f, 1f) to ((y - top()) / dispH()).coerceIn(0f, 1f)

    /** 확대 상태에서 커서가 화면 밖으로 나가면 따라가기 */
    private fun followCursor() {
        val cx = left() + cursorX * dispW()
        val cy = top() + cursorY * dispH()
        val margin = 60 * density
        var moved = false
        if (cx < margin) { panX += margin - cx; moved = true }
        if (cx > width - margin) { panX -= cx - (width - margin); moved = true }
        if (cy < margin) { panY += margin - cy; moved = true }
        if (cy > height - margin) { panY -= cy - (height - margin); moved = true }
        if (moved) applyTransform()
    }

    private fun zoomAt(factor: Float, fx: Float, fy: Float) {
        val old = zoom
        zoom = (zoom * factor).coerceIn(1f, 6f)
        val f = zoom / old
        // 초점(fx,fy)이 같은 자리에 머물도록 이동량 조정 (중심 기준 좌표)
        val cx = width / 2f + panX
        val cy = height / 2f + panY
        panX += (fx - cx) * (1 - f)
        panY += (fy - cy) * (1 - f)
        applyTransform()
    }

    // ------------------------------------------------------------ 커서 그리기
    private val cursorPath = Path().apply {
        moveTo(0f, 0f); lineTo(0f, 17f); lineTo(4.2f, 13f); lineTo(7f, 19.5f)
        lineTo(9.8f, 18.3f); lineTo(7.1f, 12f); lineTo(12.6f, 12f); close()
    }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; style = Paint.Style.FILL }
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.BLACK; style = Paint.Style.STROKE; strokeWidth = 1.2f; strokeJoin = Paint.Join.ROUND
    }

    override fun onDrawForeground(canvas: Canvas) {
        super.onDrawForeground(canvas)
        if (cursorX < 0 || frameW == 0) return
        if (cursorX > 1f || cursorY > 1f || cursorY < 0f) return
        val x = left() + cursorX * dispW()
        val y = top() + cursorY * dispH()
        canvas.save()
        canvas.translate(x, y)
        val s = density * 1.1f
        canvas.scale(s, s)
        canvas.drawPath(cursorPath, fill)
        canvas.drawPath(cursorPath, stroke)
        canvas.restore()
    }

    override fun onSizeChanged(w: Int, h: Int, ow: Int, oh: Int) {
        super.onSizeChanged(w, h, ow, oh)
        post { applyTransform() }
    }

    // ------------------------------------------------------------ 터치 처리
    private enum class Two { NONE, SCROLL, PINCH }

    private var downX = 0f; private var downY = 0f; private var downTime = 0L
    private var lastX = 0f; private var lastY = 0f
    private var moved = false
    private var dragging = false
    private var longPressFired = false
    private var maxPointers = 0
    private var lastTapUp = 0L; private var lastTapX = 0f; private var lastTapY = 0f
    private var tapDragCandidate = false
    private var two = Two.NONE
    private var span0 = 0f; private var mid0X = 0f; private var mid0Y = 0f
    private var lastSpan = 0f; private var lastMidX = 0f; private var lastMidY = 0f
    private var scrollAccX = 0f; private var scrollAccY = 0f
    private var lastT = 0L
    private var vEma = 0f                 // 손가락 속도 (dp/ms, 부드럽게 평균)
    private var lastLocalMove = 0L
    private var sendPending = false

    private val longPress = Runnable {
        if (moved || maxPointers > 1) return@Runnable
        longPressFired = true
        performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        if (trackpad) {
            listener.button("left", true); dragging = true   // 길게 누른 뒤 움직이면 드래그
        } else {
            val (nx, ny) = toNorm(downX, downY)
            listener.moveAbs(nx, ny)
            listener.click("right")
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(e: MotionEvent): Boolean {
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = e.x; downY = e.y; lastX = e.x; lastY = e.y
                downTime = e.eventTime
                moved = false; dragging = false; longPressFired = false
                maxPointers = 1; two = Two.NONE
                lastT = e.eventTime; vEma = 0f
                tapDragCandidate = trackpad && e.eventTime - lastTapUp < 300 &&
                    hypot(e.x - lastTapX, e.y - lastTapY) < 60 * density
                if (!trackpad) {
                    val (nx, ny) = toNorm(e.x, e.y)
                    listener.moveAbs(nx, ny)
                }
                handler.postDelayed(longPress, if (trackpad) 450L else 550L)
            }

            MotionEvent.ACTION_POINTER_DOWN -> {
                maxPointers = max(maxPointers, e.pointerCount)
                handler.removeCallbacks(longPress)
                if (dragging) { listener.button("left", false); dragging = false }
                if (e.pointerCount == 2) startTwo(e)
            }

            MotionEvent.ACTION_MOVE -> {
                if (e.pointerCount >= 2 && maxPointers >= 2) {
                    moveTwo(e)
                } else if (maxPointers == 1) {
                    moveOne(e)
                }
            }

            MotionEvent.ACTION_POINTER_UP -> {
                if (e.pointerCount == 2 && two == Two.NONE && maxPointers == 2 &&
                    e.eventTime - downTime < 350) {
                    listener.click("right")
                    two = Two.SCROLL   // 한 번만 클릭되게
                }
            }

            MotionEvent.ACTION_UP -> {
                handler.removeCallbacks(longPress)
                if (maxPointers == 1) {
                    if (dragging) {
                        listener.button("left", false)
                    } else if (!moved && !longPressFired && e.eventTime - downTime < 300) {
                        if (!trackpad) {
                            val (nx, ny) = toNorm(e.x, e.y)
                            listener.moveAbs(nx, ny)
                        }
                        listener.click("left")
                        lastTapUp = e.eventTime; lastTapX = e.x; lastTapY = e.y
                    }
                }
                dragging = false
            }

            MotionEvent.ACTION_CANCEL -> {
                handler.removeCallbacks(longPress)
                if (dragging) listener.button("left", false)
                dragging = false
            }
        }
        return true
    }

    private fun moveOne(e: MotionEvent) {
        if (!moved && hypot(e.x - downX, e.y - downY) > slop) {
            moved = true
            // 움직임 판정 전까지의 거리만큼 커서가 툭 튀지 않도록 여기서부터 셈
            lastX = e.x; lastY = e.y; lastT = e.eventTime
            if (!longPressFired) handler.removeCallbacks(longPress)
            if (trackpad && tapDragCandidate && !dragging) {      // 두 번 탭 후 끌기 = 드래그
                listener.button("left", true); dragging = true
            }
            if (!trackpad && !longPressFired) {                  // 터치 모드: 누른 곳부터 드래그
                val (nx, ny) = toNorm(downX, downY)
                listener.moveAbs(nx, ny)
                listener.button("left", true); dragging = true
            }
        }
        if (!moved) return
        if (trackpad) {
            // 터치 사이사이의 중간 지점까지 모두 반영해 매끄럽게
            for (i in 0..e.historySize) {
                val x = if (i < e.historySize) e.getHistoricalX(i) else e.x
                val y = if (i < e.historySize) e.getHistoricalY(i) else e.y
                val t = if (i < e.historySize) e.getHistoricalEventTime(i) else e.eventTime
                trackpadDelta(x - lastX, y - lastY, t - lastT)
                lastX = x; lastY = y; lastT = t
            }
            return
        } else if (dragging) {
            val (nx, ny) = toNorm(e.x, e.y)
            cursorX = nx; cursorY = ny
            scheduleSend()
        }
        lastX = e.x; lastY = e.y
    }

    /**
     * 트랙패드 이동: 휴대폰이 커서를 먼저 옮겨 그리고(지연 없음), PC에는 그 위치를 화면 갱신 주기마다 보냄.
     * 가속: 천천히 움직이면 정밀하게(0.5배), 빠르게 밀면 멀리(최대 2.6배) — 속도는 부드럽게 평균 냄.
     */
    private fun trackpadDelta(dx: Float, dy: Float, dt: Long) {
        if (dx == 0f && dy == 0f) return
        if (dispW() <= 0f) return
        val v = hypot(dx, dy) / density / max(dt, 1L).toFloat()
        vEma = vEma * 0.5f + v * 0.5f
        val gain = speed * accelCurve(vEma)
        if (cursorX !in 0f..1f || cursorY !in 0f..1f) { cursorX = 0.5f; cursorY = 0.5f }
        cursorX = (cursorX + dx / dispW() * gain).coerceIn(0f, 1f)
        cursorY = (cursorY + dy / dispH() * gain).coerceIn(0f, 1f)
        lastLocalMove = SystemClock.uptimeMillis()
        if (zoom > 1.01f) followCursor()
        invalidate()
        scheduleSend()
    }

    /** 손가락 속도(dp/ms) → 배율. 천천히는 작게(정밀), 빠를수록 가파르게 커짐 */
    private fun accelCurve(v: Float): Float = when (accel) {
        0 -> (0.5f + 1.0f * v).coerceIn(0.5f, 2.6f)
        2 -> (0.25f + 0.6f * v + 1.2f * v * v).coerceIn(0.25f, 6.0f)
        else -> (0.35f + 0.8f * v + 0.6f * v * v).coerceIn(0.35f, 4.0f)
    }

    /** 여러 터치 신호를 묶어 화면 한 번 갱신될 때마다 최신 위치만 보냄 */
    private fun scheduleSend() {
        if (sendPending) return
        sendPending = true
        postOnAnimation {
            sendPending = false
            listener.moveAbs(cursorX, cursorY)
        }
    }

    private fun startTwo(e: MotionEvent) {
        span0 = span(e); lastSpan = span0
        mid0X = (e.getX(0) + e.getX(1)) / 2; mid0Y = (e.getY(0) + e.getY(1)) / 2
        lastMidX = mid0X; lastMidY = mid0Y
        scrollAccX = 0f; scrollAccY = 0f
    }

    private fun moveTwo(e: MotionEvent) {
        val sp = span(e)
        val mx = (e.getX(0) + e.getX(1)) / 2
        val my = (e.getY(0) + e.getY(1)) / 2
        if (two == Two.NONE) {
            if (abs(sp - span0) > 40 * density) two = Two.PINCH
            else if (hypot(mx - mid0X, my - mid0Y) > 14 * density) two = Two.SCROLL
        }
        when (two) {
            Two.PINCH -> {
                if (lastSpan > 0) zoomAt(sp / lastSpan, mx, my)
                panX += mx - lastMidX; panY += my - lastMidY
                applyTransform()
            }
            Two.SCROLL -> {
                // 손가락을 위로 올리면 내용이 위로 (휴대폰과 같은 '자연스러운 스크롤')
                scrollAccY += (my - lastMidY) * 4f / density
                scrollAccX += (mx - lastMidX) * 4f / density
                val sy = scrollAccY.toInt(); val sx = scrollAccX.toInt()
                if (abs(sy) >= 15 || abs(sx) >= 15) {
                    listener.wheel(if (abs(sy) >= 15) sy else 0, if (abs(sx) >= 15) -sx else 0)
                    if (abs(sy) >= 15) scrollAccY -= sy
                    if (abs(sx) >= 15) scrollAccX -= sx
                }
            }
            Two.NONE -> {}
        }
        lastSpan = sp; lastMidX = mx; lastMidY = my
    }

    private fun span(e: MotionEvent) = hypot(e.getX(0) - e.getX(1), e.getY(0) - e.getY(1))
}
