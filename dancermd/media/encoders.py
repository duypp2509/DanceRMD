"""JPEG and H.264 encoders producing binary frames for the phone.

Each frame sent over the WebSocket starts with one type byte (see FRAME_*); docs/protocol.md has
the full format. All functions run on the capture thread.
"""

import io
import logging
from fractions import Fraction

import numpy as np
from PIL import Image

try:
    import av
    from av.video.reformatter import Interpolation, VideoReformatter
except Exception:  # PyAV missing or broken: JPEG only
    av = None

log = logging.getLogger(__name__)

# Quality presets: maximum width sent, JPEG quality, H.264 bitrate
QUALITY = {
    "low": {"width": 1280, "jpeg": 45, "bitrate": 1_500_000},
    "medium": {"width": 1600, "jpeg": 60, "bitrate": 4_000_000},
    "high": {"width": 2560, "jpeg": 75, "bitrate": 10_000_000},
}
FRAME_JPEG, FRAME_H264_KEY, FRAME_H264_DELTA = 1, 2, 3

# H.264 encoders in order of preference: hardware first, CPU last
H264_ENCODERS = (
    ("h264_nvenc", "NVIDIA NVENC",
     {"preset": "p3", "tune": "ull", "zerolatency": "1", "rc": "cbr", "delay": "0", "forced-idr": "1"}),
    ("h264_qsv", "Intel Quick Sync", {"preset": "veryfast", "async_depth": "1", "forced_idr": "1"}),
    ("h264_amf", "AMD AMF", {"usage": "ultralowlatency", "quality": "speed", "header_insertion_mode": "idr"}),
    ("libx264", "CPU (x264)", {"preset": "ultrafast", "tune": "zerolatency", "forced-idr": "1"}),
)
_h264_choice = None  # (name, label, options) | False, probed once


def even_size(w, h, max_width):
    """Scale (w, h) down to max_width keeping the aspect ratio; H.264 needs even dimensions."""
    if w > max_width:
        h, w = round(h * max_width / w), max_width
    return w - w % 2, h - h % 2


def codec_string(data):
    """WebCodecs codec string (e.g. "avc1.640033") read from the SPS of an Annex B H.264 packet."""
    i = 0
    while (i := data.find(b"\x00\x00\x01", i)) >= 0 and i + 7 <= len(data):
        if data[i + 3] & 0x1F == 7:  # NAL unit type 7: sequence parameter set
            return f"avc1.{data[i + 4]:02X}{data[i + 5]:02X}{data[i + 6]:02X}"
        i += 3
    return None


def _key_picture():
    try:
        return av.video.frame.PictureType.I
    except AttributeError:  # older PyAV
        return "I"


def _open_h264(name, options, width, height, bitrate):
    ctx = av.CodecContext.create(name, "w")
    ctx.width, ctx.height = width, height
    ctx.pix_fmt = "yuv420p" if name == "libx264" else "nv12"
    ctx.time_base = Fraction(1, 1000)
    ctx.framerate = Fraction(30, 1)
    ctx.bit_rate = bitrate
    ctx.gop_size = 3000   # keyframes are requested explicitly (new viewer, monitor switch, decoder reset)
    ctx.max_b_frames = 0  # B-frames add latency
    ctx.options = dict(options)
    ctx.open()
    return ctx


def pick_h264():
    """The best H.264 encoder this machine can open: (name, label, options), or None."""
    global _h264_choice
    if _h264_choice is None:
        _h264_choice = False
        if av is not None:
            probe = np.zeros((360, 640, 4), np.uint8)
            for name, label, options in H264_ENCODERS:
                try:
                    ctx = _open_h264(name, options, 640, 360, 1_000_000)
                    frame = av.VideoFrame.from_ndarray(probe, format="bgra").reformat(format=ctx.pix_fmt)
                    frame.pts = 0
                    if ctx.encode(frame):
                        _h264_choice = (name, label, options)
                        log.info("H.264 encoder: %s", label)
                        break
                except Exception as exc:
                    log.debug("%s unavailable: %s", name, exc)
    return _h264_choice or None


def h264_label():
    choice = pick_h264()
    return choice[1] if choice else None


class JpegEncoder:
    codec = "jpeg"
    label = "JPEG"

    def __init__(self, quality):
        self.quality = quality

    def encode(self, frame, keyframe=False):
        h, w = frame.shape[:2]
        img = Image.frombuffer("RGB", (w, h), frame, "raw", "BGRX", 0, 1)
        size = even_size(w, h, QUALITY[self.quality]["width"])
        if size != (w, h):
            img = img.resize(size, Image.BILINEAR, reducing_gap=2.0)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=QUALITY[self.quality]["jpeg"])
        return [(FRAME_JPEG, buf.getvalue())]

    def take_config(self):
        return None


class H264Encoder:
    codec = "h264"

    def __init__(self, quality):
        self.quality = quality
        self.name, self.label, self.options = pick_h264()
        self.ctx = None
        self.size = None
        self.pts = 0
        self._config = None                # decoder configuration waiting to be sent to the phone
        self._scaler = VideoReformatter()  # reused so the scaler isn't rebuilt every frame

    def encode(self, frame, keyframe=False):
        h, w = frame.shape[:2]
        size = even_size(w, h, QUALITY[self.quality]["width"])
        if size != self.size:  # monitor or resolution changed: reopen the encoder
            self.ctx = _open_h264(self.name, self.options, *size, QUALITY[self.quality]["bitrate"])
            self.size = size
            keyframe = True
        vf = av.VideoFrame.from_ndarray(frame, format="bgra")
        # AREA keeps text crisp when downscaling high-resolution screens
        vf = self._scaler.reformat(vf, width=size[0], height=size[1], format=self.ctx.pix_fmt,
                                   interpolation=Interpolation.AREA)
        vf.pts = self.pts
        self.pts += 33
        if keyframe:
            vf.pict_type = _key_picture()
        out = []
        for packet in self.ctx.encode(vf):
            data = bytes(packet)
            if packet.is_keyframe:
                codec = codec_string(data)
                if codec and (self._config is None or self._config.get("config") != codec or keyframe):
                    self._config = {"t": "video", "codec": "h264", "config": codec,
                                    "width": size[0], "height": size[1], "encoder": self.label}
            out.append((FRAME_H264_KEY if packet.is_keyframe else FRAME_H264_DELTA, data))
        return out

    def take_config(self):
        config, self._config = self._config, None
        return config


def make_encoder(codec, quality):
    if codec == "h264" and pick_h264():
        return H264Encoder(quality)
    return JpegEncoder(quality)
