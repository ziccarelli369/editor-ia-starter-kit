"""filmkit.sound: synthesis, mixing, mastering and measurement. Owner: sound. Needs the kit venv
(numpy, scipy, pedalboard). Never imported by Blender.

Signals are float64 numpy arrays: mono (n,) or stereo (2, n). Sample rate is
48000 everywhere (asserted where BS.1770 coefficients are used). Levels in
dBFS, loudness in LUFS. Every generator is a pure function of (params, seed)
and returns a buffer whose transient starts on sample 0.
"""
SR = 48000
