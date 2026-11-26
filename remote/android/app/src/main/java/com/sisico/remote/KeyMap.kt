package com.sisico.remote

import android.view.KeyEvent

/** 윈도우 가상 키 코드와, 안드로이드 물리 키보드 → 윈도우 키 변환표. */
object VK {
    const val BACK = 0x08; const val TAB = 0x09; const val ENTER = 0x0D
    const val SHIFT = 0xA0; const val CTRL = 0xA2; const val ALT = 0xA4
    const val ESC = 0x1B; const val SPACE = 0x20
    const val PGUP = 0x21; const val PGDN = 0x22; const val END = 0x23; const val HOME = 0x24
    const val LEFT = 0x25; const val UP = 0x26; const val RIGHT = 0x27; const val DOWN = 0x28
    const val PRTSC = 0x2C; const val INS = 0x2D; const val DEL = 0x2E
    const val WIN = 0x5B; const val APPS = 0x5D
    const val F1 = 0x70
    const val HANGUL = 0x15; const val HANJA = 0x19
    const val VOL_MUTE = 0xAD; const val VOL_DOWN = 0xAE; const val VOL_UP = 0xAF
    const val MEDIA_NEXT = 0xB0; const val MEDIA_PREV = 0xB1; const val MEDIA_PLAY = 0xB3

    fun letter(c: Char): Int? = when (c.uppercaseChar()) {
        in 'A'..'Z' -> c.uppercaseChar().code
        in '0'..'9' -> c.code
        else -> null
    }

    fun fromAndroid(code: Int): Int? = when (code) {
        in KeyEvent.KEYCODE_A..KeyEvent.KEYCODE_Z -> 0x41 + (code - KeyEvent.KEYCODE_A)
        in KeyEvent.KEYCODE_0..KeyEvent.KEYCODE_9 -> 0x30 + (code - KeyEvent.KEYCODE_0)
        in KeyEvent.KEYCODE_F1..KeyEvent.KEYCODE_F12 -> F1 + (code - KeyEvent.KEYCODE_F1)
        in KeyEvent.KEYCODE_NUMPAD_0..KeyEvent.KEYCODE_NUMPAD_9 -> 0x60 + (code - KeyEvent.KEYCODE_NUMPAD_0)
        KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> ENTER
        KeyEvent.KEYCODE_DEL -> BACK
        KeyEvent.KEYCODE_FORWARD_DEL -> DEL
        KeyEvent.KEYCODE_TAB -> TAB
        KeyEvent.KEYCODE_SPACE -> SPACE
        KeyEvent.KEYCODE_ESCAPE -> ESC
        KeyEvent.KEYCODE_SHIFT_LEFT -> SHIFT
        KeyEvent.KEYCODE_SHIFT_RIGHT -> 0xA1
        KeyEvent.KEYCODE_CTRL_LEFT -> CTRL
        KeyEvent.KEYCODE_CTRL_RIGHT -> 0xA3
        KeyEvent.KEYCODE_ALT_LEFT -> ALT
        KeyEvent.KEYCODE_ALT_RIGHT -> 0xA5
        KeyEvent.KEYCODE_META_LEFT, KeyEvent.KEYCODE_META_RIGHT -> WIN
        KeyEvent.KEYCODE_DPAD_LEFT -> LEFT
        KeyEvent.KEYCODE_DPAD_RIGHT -> RIGHT
        KeyEvent.KEYCODE_DPAD_UP -> UP
        KeyEvent.KEYCODE_DPAD_DOWN -> DOWN
        KeyEvent.KEYCODE_MOVE_HOME -> HOME
        KeyEvent.KEYCODE_MOVE_END -> END
        KeyEvent.KEYCODE_PAGE_UP -> PGUP
        KeyEvent.KEYCODE_PAGE_DOWN -> PGDN
        KeyEvent.KEYCODE_INSERT -> INS
        KeyEvent.KEYCODE_SYSRQ -> PRTSC
        KeyEvent.KEYCODE_CAPS_LOCK -> 0x14
        KeyEvent.KEYCODE_MENU -> APPS
        KeyEvent.KEYCODE_KANA, KeyEvent.KEYCODE_LANGUAGE_SWITCH -> HANGUL
        KeyEvent.KEYCODE_MINUS -> 0xBD
        KeyEvent.KEYCODE_EQUALS -> 0xBB
        KeyEvent.KEYCODE_LEFT_BRACKET -> 0xDB
        KeyEvent.KEYCODE_RIGHT_BRACKET -> 0xDD
        KeyEvent.KEYCODE_BACKSLASH -> 0xDC
        KeyEvent.KEYCODE_SEMICOLON -> 0xBA
        KeyEvent.KEYCODE_APOSTROPHE -> 0xDE
        KeyEvent.KEYCODE_GRAVE -> 0xC0
        KeyEvent.KEYCODE_COMMA -> 0xBC
        KeyEvent.KEYCODE_PERIOD -> 0xBE
        KeyEvent.KEYCODE_SLASH -> 0xBF
        KeyEvent.KEYCODE_NUMPAD_ADD -> 0x6B
        KeyEvent.KEYCODE_NUMPAD_SUBTRACT -> 0x6D
        KeyEvent.KEYCODE_NUMPAD_MULTIPLY -> 0x6A
        KeyEvent.KEYCODE_NUMPAD_DIVIDE -> 0x6F
        KeyEvent.KEYCODE_NUMPAD_DOT -> 0x6E
        else -> null
    }
}
