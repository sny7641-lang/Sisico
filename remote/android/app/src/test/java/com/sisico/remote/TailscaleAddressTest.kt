package com.sisico.remote

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TailscaleAddressTest {
    @Test
    fun recognisesTailscaleAddresses() {
        assertTrue(TailscaleControl.needed("100.109.132.65"))
        assertTrue(TailscaleControl.needed("100.64.0.1"))
        assertTrue(TailscaleControl.needed("100.127.255.254"))
        assertTrue(TailscaleControl.needed("my-pc.tail1234.ts.net"))
        assertTrue(TailscaleControl.needed("fd7a:115c:a1e0::1"))
    }

    @Test
    fun ignoresOtherAddresses() {
        assertFalse(TailscaleControl.needed("192.168.219.163"))
        assertFalse(TailscaleControl.needed("100.128.0.1"))
        assertFalse(TailscaleControl.needed("100.63.0.1"))
        assertFalse(TailscaleControl.needed("10.0.0.5"))
    }
}
