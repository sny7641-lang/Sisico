package com.sisico.remote

import android.app.Activity
import android.app.AlertDialog
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.util.TypedValue
import android.webkit.MimeTypeMap
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import org.json.JSONObject
import java.io.File
import java.io.OutputStream

/**
 * 파일 주고받기.
 *  - 휴대폰 → PC: 파일을 골라 PC의 '다운로드\Sisico 원격' 폴더로 보냄
 *  - PC → 휴대폰: PC 폴더를 둘러보고 파일을 휴대폰 '다운로드/Sisico 원격' 에 저장
 */
class FileTransfer(private val act: Activity, private val client: () -> RemoteClient?) {

    companion object {
        const val PICK_REQUEST = 7001
        private const val CHUNK = 256 * 1024
        private const val MAX_QUEUED = 2L * 1024 * 1024
    }

    private val ui = Handler(Looper.getMainLooper())
    private var progress: AlertDialog? = null
    private var progressBar: ProgressBar? = null
    private var progressText: TextView? = null
    @Volatile private var uploadCancelled = false
    private var uploadsLeft = 0

    // 받는 중인 파일
    private var out: OutputStream? = null
    private var outUri: Uri? = null
    private var outFile: File? = null
    private var outName = ""
    private var outSize = 0L
    @Volatile private var outGot = 0L
    private var lastPath = ""

    fun showMenu() {
        AlertDialog.Builder(act).setTitle("파일")
            .setItems(arrayOf("휴대폰 → PC 로 보내기", "PC 파일 받기")) { _, i ->
                if (i == 0) pickFile() else browse(lastPath)
            }.show()
    }

    // ================================================================ 휴대폰 → PC
    private fun pickFile() {
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
            .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
        act.startActivityForResult(i, PICK_REQUEST)
    }

    /** RemoteActivity.onActivityResult 에서 호출 */
    fun onPicked(data: Intent?) {
        val uris = ArrayList<Uri>()
        data?.clipData?.let { c -> for (k in 0 until c.itemCount) uris.add(c.getItemAt(k).uri) }
        if (uris.isEmpty()) data?.data?.let { uris.add(it) }
        if (uris.isEmpty()) return
        uploadCancelled = false
        uploadsLeft = uris.size
        showProgress("PC로 보내는 중") { uploadCancelled = true; client()?.msg("fput_cancel") }
        Thread { uris.forEachIndexed { n, u -> if (!uploadCancelled) upload(u, n + 1, uris.size) } }.start()
    }

    private fun upload(uri: Uri, index: Int, count: Int) {
        val c = client() ?: return
        var name = "file"
        var size = -1L
        act.contentResolver.query(uri, null, null, null, null)?.use { cur ->
            if (cur.moveToFirst()) {
                val ni = cur.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val si = cur.getColumnIndex(OpenableColumns.SIZE)
                if (ni >= 0) name = cur.getString(ni) ?: name
                if (si >= 0 && !cur.isNull(si)) size = cur.getLong(si)
            }
        }
        val label = if (count > 1) "($index/$count) $name" else name
        try {
            act.contentResolver.openInputStream(uri)!!.use { input ->
                c.msg("fput", "name" to name, "size" to size)
                val buf = ByteArray(CHUNK)
                var sent = 0L
                while (!uploadCancelled) {
                    val n = input.read(buf)
                    if (n <= 0) break
                    while (c.queued() > MAX_QUEUED && !uploadCancelled) Thread.sleep(15)
                    val pkt = ByteArray(n + 1)
                    pkt[0] = 0x10
                    System.arraycopy(buf, 0, pkt, 1, n)
                    if (!c.sendBinary(pkt)) { uploadCancelled = true; break }
                    sent += n
                    updateProgress(label, sent, size)
                }
                if (!uploadCancelled) c.msg("fput_end")
            }
        } catch (e: Exception) {
            c.msg("fput_cancel")
            ui.post { closeProgress(); toast("보내지 못했습니다: ${e.message}") }
        }
    }

    // ================================================================ PC → 휴대폰
    private fun browse(path: String) {
        client()?.msg("ls", "path" to path)
    }

    private fun showListing(m: JSONObject) {
        if (m.has("error")) {
            toast(m.getString("error"))
            if (m.optString("path") == lastPath) lastPath = ""
            return
        }
        val path = m.optString("path")
        lastPath = path
        val items = m.optJSONArray("items")
        val labels = ArrayList<String>()
        val actions = ArrayList<() -> Unit>()
        if (path.isNotEmpty()) {
            val parent = if (m.isNull("parent")) "" else m.optString("parent")
            labels.add("⬆  상위 폴더"); actions.add { browse(parent) }
        }
        if (items != null) for (k in 0 until items.length()) {
            val it = items.getJSONObject(k)
            val p = it.getString("path")
            if (it.optBoolean("dir")) {
                labels.add("📁  " + it.getString("name")); actions.add { browse(p) }
            } else {
                labels.add("📄  " + it.getString("name") + "   " + human(it.optLong("size")))
                actions.add { confirmDownload(it.getString("name"), p, it.optLong("size")) }
            }
        }
        if (labels.isEmpty()) labels.add("(빈 폴더)").also { actions.add {} }
        AlertDialog.Builder(act).setTitle(if (path.isEmpty()) "PC" else path)
            .setItems(labels.toTypedArray()) { _, i -> actions[i]() }
            .setNegativeButton("닫기", null).show()
    }

    private fun confirmDownload(name: String, path: String, size: Long) {
        AlertDialog.Builder(act).setMessage("$name (${human(size)}) 을(를) 휴대폰에 받을까요?")
            .setPositiveButton("받기") { _, _ ->
                showProgress("받는 중") { client()?.msg("fget_cancel") }
                client()?.msg("fget", "path" to path)
            }
            .setNegativeButton("취소") { _, _ -> browse(lastPath) }.show()
    }

    private fun openOutput(name: String): Boolean {
        outName = name
        return try {
            if (Build.VERSION.SDK_INT >= 29) {
                val ext = name.substringAfterLast('.', "").lowercase()
                val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext) ?: "application/octet-stream"
                val v = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, name)
                    put(MediaStore.Downloads.MIME_TYPE, mime)
                    put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Sisico 원격")
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val uri = act.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v)!!
                outUri = uri
                out = act.contentResolver.openOutputStream(uri)
            } else {
                val dir = act.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)!!
                var f = File(dir, name)
                var n = 1
                while (f.exists()) { f = File(dir, name.substringBeforeLast('.') + " ($n)" + name.substring(name.substringBeforeLast('.').length)); n++ }
                outFile = f
                out = f.outputStream()
            }
            out != null
        } catch (e: Exception) {
            false
        }
    }

    private fun finishOutput(ok: Boolean) {
        try { out?.close() } catch (_: Exception) {}
        out = null
        outUri?.let { uri ->
            if (ok) act.contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
            else act.contentResolver.delete(uri, null, null)
        }
        if (!ok) outFile?.delete()
        val where = if (outUri != null) "다운로드/Sisico 원격" else outFile?.parent ?: ""
        outUri = null; outFile = null
        if (ok) ui.post { closeProgress(); toast("저장했습니다: $where/$outName") }
    }

    /** 네트워크 스레드에서 불림: 파일 조각 */
    fun onChunk(data: ByteArray, offset: Int) {
        val o = out ?: return
        try {
            o.write(data, offset, data.size - offset)
            outGot += data.size - offset
            updateProgress(outName, outGot, outSize)
        } catch (e: Exception) {
            finishOutput(false)
            client()?.msg("fget_cancel")
            ui.post { closeProgress(); toast("저장하지 못했습니다: ${e.message}") }
        }
    }

    /** 네트워크 스레드에서 불림: 파일 관련 메시지. 처리했으면 true */
    fun onMessage(m: JSONObject): Boolean {
        when (m.optString("t")) {
            "ls" -> ui.post { showListing(m) }
            "fget_start" -> {
                outSize = m.optLong("size"); outGot = 0
                if (!openOutput(m.optString("name", "file"))) {
                    client()?.msg("fget_cancel")
                    ui.post { closeProgress(); toast("휴대폰에 파일을 만들 수 없습니다") }
                }
            }
            "fget_end" -> finishOutput(true)
            "fget_err" -> {
                if (out != null) finishOutput(false)
                ui.post { closeProgress(); toast(m.optString("msg")) }
            }
            "fput_ok" -> ui.post {
                if (!uploadCancelled) toast("PC에 저장: ${m.optString("path")}")
                if (--uploadsLeft <= 0) closeProgress()
            }
            "fput_err" -> ui.post { uploadCancelled = true; closeProgress(); toast("PC에 저장하지 못했습니다: ${m.optString("msg")}") }
            else -> return false
        }
        return true
    }

    /** 연결이 끊겼을 때 */
    fun abort() {
        uploadCancelled = true
        if (out != null) finishOutput(false)
        ui.post { closeProgress() }
    }

    // ================================================================ 진행 표시
    private fun showProgress(title: String, onCancel: () -> Unit) {
        closeProgress()
        val pad = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 20f, act.resources.displayMetrics).toInt()
        val box = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL; setPadding(pad, pad / 2, pad, 0) }
        progressText = TextView(act).apply { text = "준비 중…" }
        progressBar = ProgressBar(act, null, android.R.attr.progressBarStyleHorizontal).apply { max = 1000 }
        box.addView(progressText); box.addView(progressBar)
        progress = AlertDialog.Builder(act).setTitle(title).setView(box).setCancelable(false)
            .setNegativeButton("취소") { _, _ -> onCancel(); closeProgress() }.show()
    }

    private var lastUpdate = 0L
    private fun updateProgress(label: String, done: Long, total: Long) {
        val now = System.currentTimeMillis()
        if (now - lastUpdate < 150 && done != total) return
        lastUpdate = now
        ui.post {
            progressText?.text = "$label\n${human(done)}" + if (total > 0) " / ${human(total)}" else ""
            progressBar?.isIndeterminate = total <= 0
            if (total > 0) progressBar?.progress = (done * 1000 / total).toInt()
        }
    }

    private fun closeProgress() {
        progress?.dismiss()
        progress = null; progressBar = null; progressText = null
    }

    private fun toast(s: String) = Toast.makeText(act, s, Toast.LENGTH_LONG).show()

    private fun human(n: Long): String = when {
        n >= 1L shl 30 -> "%.1f GB".format(n / 1073741824.0)
        n >= 1L shl 20 -> "%.1f MB".format(n / 1048576.0)
        n >= 1L shl 10 -> "%.0f KB".format(n / 1024.0)
        else -> "$n B"
    }
}
