"""Screen capture and video encoding.

Capture: DXGI Desktop Duplication on the GPU (dxcam), with a GDI fallback (mss) for virtual machines,
Remote Desktop sessions and the secure desktop.
Encoding: hardware H.264 (NVENC, Quick Sync, AMF) through PyAV when the phone can decode it with
WebCodecs (HTTPS only), JPEG otherwise.
"""
