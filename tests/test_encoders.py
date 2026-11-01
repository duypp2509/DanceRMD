from dancermd.media import encoders


def test_even_size_keeps_small_frames():
    assert encoders.even_size(1280, 720, 1600) == (1280, 720)


def test_even_size_scales_down_and_rounds_to_even():
    assert encoders.even_size(2560, 1600, 1600) == (1600, 1000)
    w, h = encoders.even_size(1921, 1081, 1600)
    assert w % 2 == 0 and h % 2 == 0 and w <= 1600


def test_codec_string_reads_profile_from_sps():
    # Annex B: an SPS (NAL type 7) with profile 0x64 (High), constraints 0x00, level 0x33 (5.1)
    packet = b"\x00\x00\x00\x01\x67\x64\x00\x33\xac" + b"\x00\x00\x01\x68\xee"
    assert encoders.codec_string(packet) == "avc1.640033"


def test_codec_string_without_sps():
    assert encoders.codec_string(b"\x00\x00\x01\x65\x88\x84\x00\x10") is None


def test_quality_presets_are_ordered():
    widths = [encoders.QUALITY[q]["width"] for q in ("low", "medium", "high")]
    assert widths == sorted(widths)


def test_jpeg_encoder_produces_typed_frame():
    import numpy as np

    frame = np.zeros((90, 160, 4), np.uint8)
    out = encoders.JpegEncoder("low").encode(frame)
    assert len(out) == 1
    kind, data = out[0]
    assert kind == encoders.FRAME_JPEG and data[:2] == b"\xff\xd8"
