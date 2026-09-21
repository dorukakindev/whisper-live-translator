# Derin eş-zamanlılık / yaşam-döngüsü / hata-enjeksiyonu denetimi (2026-09-21)

Kapsam: `buyedektir.py` canlı-oturum durum makinesi ve çevresindeki tüm asenkron
sınırlar — yakalama yaşam döngüsü (A), transkripsiyon boru hattı (B), üç PTT yolu
(C), offload edilmiş/gecikmiş işler (D), dosya ve kalıcı durum güvenliği (E).

Tüm deneyler Ubuntu üzerinde, uygulamanın kendi arayüzlerine bağlanmış
deterministik sahtelerle (`_FakeModel`, `threading.Event` kapılı akışlar,
kontrollü executor'lar, kilit sondaları) yapıldı; kanıt olarak keyfi `sleep`
kullanılmadı. Donanım gerektiren yollar (PyAudio, CUDA) sahtelendi — bu
kısımların simüle edilmiş kanıt olduğu, gerçek donanım kanıtı olmadığı açıkça
ayrıldı.

## Doğrulanmış hatalar ve düzeltmeler

Her biri için önce deterministik olarak başarısız olan regresyon testi yazıldı,
sonra düzeltme uygulandı, test yeniden koştu. Test dosyası:
`tests/test_concurrency_audit.py` (smoke'a kalıcı olarak bağlandı).

| # | Yer | Hata | Etki | Düzeltme | Test |
|---|-----|------|------|----------|------|
| B-1a | `push_to_talk` (`/api/ptt`) | `type(sequence) is int` geçmediyse `active=true` sahiplik denetimini tamamen atlıyor, `ptt_active` koşulsuz yazılıyordu | Sırasız/bozuk istemci her an PTT'yi açabiliyordu; sahiplik/sıralama koruması fiilen devre dışı | `elif active:` kolu: koşan capture'da `stale`, durmussa 409; sırasız stop değişmeden koşulsuz uygulanır | `test_unsequenced_start_never_applies` (7 varyant + 409 dalı) |
| B-1b | `push_to_talk` | `is_running` kontrolü sahiplik kaydından SONRA yapılıyordu: 409 alan yeni istemci yine de sahiplik alıp eskiyi emekliye ayırıyordu | Tek bir erken/başarısız start ile eski sayfa kalıcı olarak kilitleniyordu (stop'ları hep stale'e düşüyordu) | 409 kontrolü kayıt/ölüm işleminden ÖNCE; sahiplik yalnız uygulanan komutta güncellenir | `test_rejected_start_does_not_steal_ownership` |
| B-1c | `push_to_talk` | `_ptt_sequences` ve `_ptt_retired_clients` keyfi `source` dizgileriyle sınırsız büyüyordu | `source` flood'u ile bellek/CPU büyümesi (DoS yüzeyi) | Kaynak haritaları 16 girişle sınırlı (insertion-oldest tahliye); per-client deque zaten 64 sınırlı | `test_ptt_bookkeeping_bounded_per_source` |
| B-2 | `_transcribe_audio` | `translate_executor.submit` korumasızdı: executor kapanmışsa istisna yukarı fırlıyor, kayıt `translation_status='pending'` kalıyordu | UI'da sonsuz "çevriliyor" bekleme durumu; hata eventi kayıp | submit try/except'e sarıldı; redde düşerse kayıt `failed` + `transcription_translation_status` emit edilir | `test_translate_submit_failure_emits_terminal` |
| B-3 | `_transcribe_audio` | `diarize_executor.submit` reddi `raise`'e gidiyor → `except Exception` kola → kullanıcıya "yazıya dönüştürme hatası" emit ediliyordu — oysa transkript çoktan commit edilmişti | Başarılı konuşma için sahte hata uyarısı; `_diarize_slot` release edilse de anlamsız `error` emit'i | Submit reddi loglanır, slot bırakılır, `raise` yok | `test_diarize_submit_failure_is_silent` |
| B-4 | `MicRecorder._record` | `stream.read` istisnası yalnız loglanıp `break` ediliyordu — hiç socket emit yoktu (120 sn sınırı emit ediyordu, okuma hatası etmiyordu) | Alt basılıyken cihaz düşerse konuşma sessizce kayboluyor; UI'da "dinleniyor" kalıyor | `is_recording` hala doğruysa kullanıcıya `error` event'i emit edilir | `test_mic_read_failure_notifies_user` |
| B-5/E | `_transcribe_audio`, `_translate_async`, `process_mic_audio` | `_append_transcript` (tmp yaz + fsync + `os.replace`) `_lifecycle_lock` ALTINDA çalışıyordu (3 yerde) | Yavaş/takılan disk yazımı stop/reset/başlat/düzeltme/snapshot'ı hepsini blokluyordu | Satır kilit içinde hazırlanıyor; `os.replace`'li yazma işi kilit serbest bırakıldıktan sonra | `test_*_outside_lock` (3 site) |
| B-5b/E | `SpeakerDiarizer.save_profiles` + çağırıcıları | `save_profiles` tmp yazımı + `os.replace`'i `_profile_lock` altında yapıyordu; `identify_speaker`, `update_speaker_name`, `reset` ve `hf_token` rotası kilit tutarken disk I/O çağırıyordu | Yavaş diskte konuşmacı tanıma ve isim güncellemeleri kilitleniyor | `save_profiles` payload'u `_profile_lock` içinde snapshot'layıp yazımı o kilidin dışına taşıdı; **aynı zamanda** snapshot+yazım toplamı yeni `_profile_write_lock` ile serileştirildi — aksi halde geciken eski yazici yeni güncellemeyi ezerdi (kayıp güncelleme, PR incelemesinde bulundu) | `test_speaker_profile_write_outside_lock` + `test_profile_save_delayed_writer_cannot_overwrite_newer` |
| B-6 | `_ptt_mic_command` | İptal edilmiş `recording_id` ile `start` `{'success': True, 'discarded': True}` dönüyordu | Frontend `.then()` `discarded`'ı kontrol etmeden "dinleniyor" gösteriyordu — sahte başarı | Açık `{'success': False, 'error': ...}` + HTTP 409 | `test_cancelled_recording_id_start_is_rejected` |
| B-7 | `process_mic_audio` | Başarı emit'i (`socketio.emit` içinde) istisna atarsa dış `except` kolu ikinci bir `ptt_mic_result` (hata) emit ediyordu | Aynı `recording_id` için success+error çift terminal — UI dedup'ı yakalayamaz (dedup yalnız `success` kayıtlara bakar) | `terminal_sent` bayrağı: kayıt `transcriptions`'a girdiği anda set; hata emit'i bayrak yoksa tek sefer | `test_mic_result_at_most_one_terminal` |
| B-8 | `_ptt_mic_command` | `result_generation` `mic_recorder.stop()` SONRASI örnekleniyordu — `stop()` ~1.5 sn join beklerken araya giren Stop/Reset yakalanamıyordu | Stop/Reset sonrası giden sonuç `transcriptions` + dosya + DOM'a sızıyordu | Nesil örneklemi `stop()` çağrısından ÖNCE `_lifecycle_lock` altına alındı | `test_mic_stop_during_stop_capture_is_stale` |

## Reddedilen yanlış pozitifler (statik şüphe → test ile doğrulanmış değil)

- `audio_queue` eski öğe düşürme: `queue.Full` kolunda `transcription_lagging` emit + `stats` düşürme var; kaybolan öğe kullanıcıya bildiriliyor — hata değil, tasarım.
- `_mic_job_slots` sayacı: reserve/transfer/release akışı dengeli — sahte-future
  üzerinde over-release yalnız slot hiç tutulmadan çağrılırsa olur; gerçek akışta
  ulaşılamaz (test edildi).
- `_lifecycle_lock` ↔ `_command_lock` sıralaması: iki yön de tek yönde tutarlı
  (`command → lifecycle`); ters sırada alım yok — inversiyon yok.
- Eski transkript işçisinin kuyruk soygunu: eski thread'ler hayattayken yeni start
  reddediliyor; sızıntı senaryosu üretilemedi.
- `_partial_inflight` oturum kapısı + `_utterance_seq` bayatlaması: mevcut
  koruma doğru çalışıyor (mevcut smoke testleri geçiyor).
- `_slot_reservation_timer` ezilmesi: zamanlayıcı üzerine yazım zararsız —
  eski timer `recording_id` eşleşmesi kontrolüyle kendini devre dışı bırakıyor.
- Frontend bayat-sonuç korumaları (`recording_id` eşleşmesi, `_ownMicGeneration`,
  `seenTranscriptionIds`, `instance_id` resync) mevcut ve doğru.

## Deterministik durum-geçiş matrisi

- `test_ptt_command_order_matrix`: 17 el yazısı senaryo (tek/iki/üç istemci,
  stop-before-start, çift start/stop, nesil-değiştirme).
- `test_ptt_property_interleavings`: 20 deterministik tohum × 25 adım = 500
  komut; her adımda `owner` emekli setinde değil, emekli client asla yeniden
  uygulanamaz, `ptt_active` bool kalır.
- Üç-nesil sahiplik, seq=1'e dönen reload, kaynaklar-arası komutlar, eksik/boş/
  devasa/tekrar-eden client id'leri ayrı testlerde.
- Toplam anlamlı interleaving sayısı ≥ 540 (matris 17 + property 500 + diğerleri).

## Komutlar ve sonuçlar (bu çalıştırmada)

- `.venv/bin/python -m py_compile buyedektir.py transkribe.py test_smoke.py tests/test_concurrency_audit.py` → temiz
- `.venv/bin/python -m pyflakes buyedektir.py transkribe.py test_smoke.py tests/test_concurrency_audit.py` → temiz
- `.venv/bin/python test_smoke.py` → TUM TESTLER GECTI (smoke + 6 arşiv + yeni suite, 21 test)
- İnceleme sonrası takip: `save_profiles` için `_profile_write_lock` eklendi (snapshot+yazım serileştirilmesi); `test_profile_save_delayed_writer_cannot_overwrite_newer` önce eski kodda `'Eski' != 'Yeni'` ile başarısız olup düzeltme sonrası geçiyor. `__new__` ile kurulan 4 test fixture'ına yeni kilit alanı eklendi.
- `node test_*.js` (12 Electron'suz dosya) → hepsi exit 0
- Inline `<script>` blokları Jinja placeholder'ıyla → `node --check` temiz (index.html 2 blok, overlay.html 1 blok, tüm `static/*.js`, `main_helpers.js`, `preload.js`)
- `node --check main.js` → temiz
- `npm run scan` → kaynak depo güvenlik taraması temiz
- `npm run build` → **ÇALIŞMADI**: electron-packager win32 hedefi `wine64` ister; Ubuntu kutu üzerinde wine kurulu değil ve sudo yok → ortam engeli (kod değil). Kayıt: rcedit/win32metadata gereksinimi.
- Electron testleri (xvfb): `test_ui_language.js` PASS, `test_cockpit_browser.js` PASS (fixture'daki `socket = io()` stub'ı `io({auth})` çağrısına güncellendi), `test_game_overlay_native.js` PASS.
- Manuel backend smoke: `PORT=5092 WHISPER_APP_TOKEN=testtok WHISPER_SKIP_API_VERIFY=1 .venv/bin/python buyedektir.py` → `GET /` 200, `/api/stats` tokenle 200, tokensuz 403.

## Kalan Windows/manuel riskler

- Gerçek WASAPI loopback akışı (pyaudiowpatch) yalnız Windows'ta doğrulanabilir; burada sahte `PyAudio`/`stream` ile arayüz sözleşmesi test edildi.
- `npm run build` exe paketi — Windows/Wine gerekli; bu ortamda çalışmaz.
- Alt-PTT akışının uçtan uca UI etkileşimi (Electron'a basılı-Alt tuş olayları) manuel/Windows doğrulaması gerektirir; backend yolu deterministik olarak test edildi.
- Çok uzun gerçek kayıtlarda `_record` hata emit'inin tekrar davranışı (her okuma hatasında tek emit — break'ten önce bir kez) UI tarafında manuel izlenebilir.
