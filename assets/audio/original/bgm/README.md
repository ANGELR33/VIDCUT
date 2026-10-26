# Música original / licenciada del canal

Aquí va **música propia o licenciada** para el canal. No se usa stock genérico de bancos.

Estructura recomendada:

```
assets/audio/original/bgm/
  upbeat/        música energética para tecnología, IA y noticias
  cinematic/     documental, historia, ciencia
  tension/       misterio, geopolítica, terror
  ambient/       fe, reflexión, podcast
  lofi/          conversación, lifestyle
```

Formatos: `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`.

El motor la prioriza sobre la biblioteca de YouTube y las pistas sintéticas. Si no hay ninguna pista original para el mood, cae al fallback sin romper el render.

Mantén la música a un nivel bajo bajo la voz; el render aplica ducking y loudnorm EBU R128 (-16 LUFS).
