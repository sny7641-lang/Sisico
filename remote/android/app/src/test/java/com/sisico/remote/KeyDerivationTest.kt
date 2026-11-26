package com.sisico.remote

import org.junit.Assert.assertEquals
import org.junit.Test

/** PC(파이썬 hashlib.pbkdf2_hmac)와 똑같은 키가 나오는지 */
class KeyDerivationTest {
    @Test
    fun matchesPythonForKoreanPassword() {
        assertEquals("4f6d6cd96973cb4c9d15cc84e4428f8ac2cddf9dc125e64413734e29f9125d24", HostStore.deriveKey("비밀번호123", "33cecb2fd54dc07e495a2d29b08a03fe", 200_000))
    }

    @Test
    fun matchesPythonSingleIteration() {
        assertEquals("a0926c54fd3e18e3913a38566398b4fa4ba03e9c2f9d43b6da7f58095970f224", HostStore.deriveKey("password", "00ff", 1))
    }

    @Test
    fun shortFingerprint() {
        assertEquals("75AD-E8DB-6101-EB15", HostStore.shortFp("75ade8db6101eb15aaaa"))
    }
}
