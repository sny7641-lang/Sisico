package com.sisico.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class H264ParamsTest {
    @Test
    fun findsSpsAndPpsInHostKeyframe() {
        // 호스트(libx264)가 만든 실제 키프레임 앞에 패킷 헤더 2바이트를 붙인 모양
        val raw = javaClass.classLoader!!.getResourceAsStream("keyframe.h264")!!.readBytes()
        val pkt = byteArrayOf(1, 1) + raw
        val (sps, pps) = H264Decoder.findParams(pkt, 2)
        assertNotNull(sps); assertNotNull(pps)
        assertEquals(7, sps!![4].toInt() and 0x1F)
        assertEquals(8, pps!![4].toInt() and 0x1F)
    }
}
