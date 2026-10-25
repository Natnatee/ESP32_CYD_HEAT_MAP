# ESP32 CYD Thailand Heat Map — ขอบเขตโปรเจกต์

Arduino ESP32 สำหรับ CYD จอ ILI9341 320×240 พร้อม calibration, WiFi setup และ Home สองหน้าแผนที่อุณหภูมิอากาศ/PM2.5 จาก Open-Meteo วาดด้วย TFT_eSPI โดยตรง ไม่มี LVGL/PSRAM

## ลำดับการทำงาน
1. โหลด calibration จาก NVS; หากใช้ไม่ได้ ให้แตะวงกลม 4 มุมและบันทึกเมื่อ affine fit ผ่าน
2. เมื่อ calibration พร้อม ลอง WiFi ที่บันทึกอัตโนมัติหนึ่งครั้ง จำกัด 20 วินาที หรือให้กรอก SSID/Password ผ่านคีย์บอร์ดบนจอ
3. เข้า Home เมื่อเชื่อมสำเร็จ แสดงแผนที่อุณหภูมิอากาศที่ 2m ปัดซ้ายไป PM2.5 / ขวากลับ มีนาฬิกากรุงเทพ UTC+7 ไม่มีปุ่มหรือ hitbox `WiFi` / `Calibrate` ด้านล่าง ใช้ Serial `w` / `c` แทน
4. เฉพาะการตั้งค่าเริ่มต้น: เชื่อมล้มเหลว/หมดเวลา/Cancel กลับฟอร์มแก้ไขโดยไม่ลบค่าดีเดิม
5. WiFi หลุดหลังเข้า Home: คง map/page/settings แสดง `OFFLINE / STALE` หรือ `OFFLINE / retrying`; `reconnect_policy.h` จัด reconnect ไม่บล็อก จำกัด 20s/attempt และ backoff 5/10/20/40/80s (cap 80s) วนต่อโดยไม่กลับฟอร์มหรือเขียน NVS; สำเร็จ reset backoff, API worker ยังคง refresh/retry schedule เดิม

NTP ใช้ `pool.ntp.org` / `time.google.com` แบบไม่บล็อก ไม่รอ sync ค้างใน UI; แสดง placeholder จน epoch >= `1704067200`

## ข้อกำหนดที่คงเดิม
- ขา GPIO ตาม `README.md` และ `hardware_lib.md`; TFT rotation 3, touch canonical rotation 1
- แปลง affine/clamp ตาม canonical แล้วกลับพิกัดสำหรับ UI; calibration เก่าใช้ต่อได้
- Preferences namespace `cyd_settings`, record `cal`/`wifi` และรูปแบบ version/profile/CRC เดิมยัง compatible ไม่ต้องลบ NVS
- บันทึก calibration เมื่อผ่าน fit; บันทึก WiFi เฉพาะเชื่อมสำเร็จและข้อมูลเปลี่ยน ใช้ `WiFi.persistent(false)`
- Serial 115200 รองรับเฉพาะ `c` ลบ calibration, `w` ลบ WiFi, `t` touch diagnostics, `h` heap/stack diagnostics ไม่ log credentials

## Dependencies / Build
Dependencies ภายนอก TFT_eSPI **2.5.43**, XPT2046_Touchscreen **v1.4**, ArduinoJson **6.21.5**; platform espressif32 **6.9.0** ส่วน WiFi/HTTPClient/WiFiClientSecure/Preferences/SNTP มากับ Arduino ESP32

```bash
pio run -e cyd_ili9341
```

เลือก `cyd_st7789` ได้เฉพาะตรวจ build compatibility ไม่ใช่จอหลัก ไม่มี auto-detect

## ข้อจำกัดและความปลอดภัย
- WiFi 2.4GHz; คีย์บอร์ด ASCII ไม่รองรับ enterprise/captive portal
- Password แสดงจริงบนจอและเก็บ plaintext ใน NVS ไม่มี flash/NVS encryption; CRC ไม่ป้องกันการอ่านข้อมูล และ `w` ไม่ใช่ secure wipe
- ฟอนต์ Nunito Bold จาก Google Fonts ใช้ SIL OFL 1.1 ดู `assets/fonts/OFL.txt`

## การยืนยันผล
ผล 2026-10-25: build `cyd_ili9341` ผ่าน Flash 999,061 bytes / static RAM 58,172 bytes, loop frame 224 bytes; ลอง HTTP API จริงจากเครื่องพัฒนาทั้งสอง endpoint ได้ schema/หน่วยตรง decoder (ไม่ใช่ทดสอบ TLS บน ESP32) มี TFT_eSPI TOUCH_CS warning ตามเดิมเนื่องจากใช้ XPT2046 แยกบัส

ทดสอบ build `cyd_ili9341` และ host tests (touch mapping, saved settings, stack guard, heat-map math/asset/gesture, API decoder และ `test_ui_network.py` ที่รัน map_ui จริงด้วย recording TFT stub ตรวจ idle/error/offline/selection redraw และ reconnect timeout/backoff/recovery/timer wrap) ไม่ flash/upload/monitor; ต้องตรวจบนบอร์ด: calibration/NVS, WiFi autoattempt/Cancel/timeout/loss, ทัช/คีย์บอร์ด/gesture, NTP placeholder/UTC+7, สีและภาพแผนที่, heap/stack ต่ำสุดระหว่าง HTTPS, TLS failure/timeout/rate limit และ stale/recovery

## Watchdog: หลักฐานและการแก้ (2026-10-25)
- Log ผู้ใช้: `task_wdt` แจ้ง IDLE0 ไม่ได้รัน ขณะ CPU0 เป็น `map_network`, CPU1 เป็น IDLE1 หลัง boot ~16–18s; ยืนยัน idle starvation แต่ corrupted backtrace ระบุฟังก์ชันต้นเหตุไม่ได้
- ตรวจ framework ที่ติดตั้งจริง Arduino ESP32: `libraries/WiFiClientSecure/src/ssl_client.cpp:271–278` มี `vTaskDelay(2)` หลัง handshake คืน WANT_READ/WANT_WRITE อยู่แล้ว; TCP connect ใช้ `select()`, write retry ก็ delay ไม่ใช่ outer handshake loop ที่ไม่มี yield อย่างที่อาจคาดเดา แต่ TLS/crypto ภายใน call เดียวยังทำงานต่อเนื่องได้ ไม่มี mbedTLS C sources ในแพ็กเกจนี้ จึงยังไม่ยืนยัน crypto/lock จุดใดจาก backtrace ที่เสีย
- แก้ scheduling defect: priority 1 กัน idle priority 0 ระหว่าง CPU-bound call; ลดเฉพาะ network worker เป็น `tskIDLE_PRIORITY`, คง unpinned (`xTaskCreate`) ไม่ย้าย starvation ไป CPU1 และไม่ปิด/reset/feed watchdog แทน idle
- Config ที่ติดตั้งจริง: dual core, tick 1000Hz, `configUSE_PREEMPTION=1`, `configUSE_TIME_SLICING=1` (FreeRTOS.h default), `configIDLE_SHOULD_YIELD=0`; equal-priority worker/idle จึงมี tick-driven scheduling และ idle ไม่ yield หนี worker ทันที เพิ่ม compile-time guard ทั้งสามค่า ไม่เปลี่ยน global framework config ทั้งนี้ไม่แก้กรณี interrupts/scheduler ถูกปิดนานใน library ซึ่งยังไม่มีหลักฐาน
- เพิ่ม log แบบจำนวนคงที่ต่อ batch: GET begin/end (รวม DNS/TCP/TLS/headers), body end (รวม cleanup), decode end พร้อม elapsed ms และ stack high-water mark; ไม่ log URL/credentials ไม่มี polling logger/task เพิ่ม Timeout และ certificate validation เดิมทั้งหมด; handshake timeout ตรวจเมื่อ library คืน control ไม่ใช่ hard wall-clock deadline ระหว่าง crypto call
- ไม่เพิ่ม stack โดยเดา: build report worker frame 576 bytes, decoder 112 bytes, loop 224 bytes; ไม่ใช่ cumulative TLS stack proof คง stack 12KiB และใช้ `h`/phase logs ดู minimum free บนบอร์ด
- Validation: `pio run -e cyd_ili9341` ผ่าน Flash 999,565 / RAM 58,172 bytes พร้อม stack guard; build compatibility `cyd_st7789` ผ่าน Flash 999,509 / RAM 58,172 bytes; `git diff --check` ผ่าน; host tests ทั้ง 6 scripts ผ่าน รวม `test_network_scheduling.py` รัน actual begin() กับ task mock ตรวจ priority/stack/idempotence/create failure และทดสอบ compile rejection ของ scheduler config ที่ไม่รองรับ ไม่ใช่ ESP-IDF SMP simulation
- ยังต้องยืนยันบนบอร์ดโดยผู้ใช้: TLS success/slow/failure ให้เกินช่วง reset เดิม, phase สุดท้ายและ stack-min, offline/stale/recovery; ไม่มี flash/upload/monitor ในการแก้ครั้งนี้

## Faster fetch / descriptions (2026-10-26)
- Framework ที่ติดตั้ง: `HTTPClient::beginInternal()` เปรียบเทียบ `_host` ว่างกับ hostname ใหม่และ `disconnect(true)` เมื่อ client ถูก probe เชื่อมไว้แล้ว; GET จึงสร้าง TLS อีกครั้ง ยืนยันสาเหตุการเชื่อมซ้ำจากโค้ด
- เอา explicit `hostByName`/`tls.connect` probe ออก ให้ GET จัดการ TLS กับ CA/timeout เดิม; อ่าน `lastError` เฉพาะ `status<0` ไม่ตีความ error48 หลัง success
- COUNT=25, BATCH=COUNT, static body 16KiB + JSON heap 16KiB (mutable zero-copy); ปกติ 2 GET/2 TLS แทน 10 GET+10 probes; publish page0 ครบก่อนเรียก page1 เมื่อสำเร็จ ไม่เผยค่าบางจุด
- คง heap guards 75KB/36KB, idle scheduling guards, stack 12KiB, retry/backoff/certificate validation; reset candidate เมื่อ decode start=0 เพื่อไม่เก็บ timestamp จากรอบที่ decode ล้มเหลว
- Right panel ASCII: ชื่อหน้า/ชนิด model/หน่วย/attribution, Now=เวลาท้องถิ่นแม้ offline, Data=timestamp เก่าที่สุดของ model พร้อมวัน/เดือน, Bangkok UTC+7, Fetched=อายุหลังรับครบจาก millis ไม่ใช่เวลาที่ model update, Min/Max ของ 25 จุด และ loading/retrying/stale/offline; คง line cache/progressive map/swipe ไม่มี bottom buttons ไม่เปลี่ยน WiFi/NVS/pins
- Tests: actual fetch mock ตรวจ TLS ครั้งเดียวต่อ GET/CA/timeouts/full 25-point URL และ payload/bounded known-unknown length/truncation/429/TLS failure; decoder full batches/bounds/invalid tail; actual worker ตรวจ retry และ healthy 2-request order/publish; TFT stub ตรวจ ASCII/bounds/cache/page names/time/min/offline ไม่ใช่ hardware timing proof

- Validation 2026-10-26: ILI9341 Flash 1,001,793 / static RAM 66,548 bytes; ST7789 compatibility Flash 1,001,749 / RAM 66,548 bytes; loop frame 224 bytes. Host tests ทั้ง 7 scripts + stack guard self-test ผ่าน และ `git diff --check` ผ่าน; TOUCH_CS warning เดิม ไม่มี upload/flash/monitor/commit ต้องยืนยัน TLS duration/heap/visual panel บนบอร์ดจริง

## โมดูลแผนที่และข้อมูล
- `main.cpp`: คงพิน/rotation/calibration/NVS/WiFi เดิม; Home รับเฉพาะ swipe (tap ไม่มี action) (แนวนอน >=45px และ >2 เท่าแนวตั้ง, <=1.5s); tap เคลื่อน <=12px และ <=700ms ต้องปล่อย Connect ก่อนใช้ Home gesture
- `map_data.cpp`: worker FreeRTOS `tskIDLE_PRIORITY` (0), ไม่ pin core, stack 12KiB, TLS client ครั้งละหนึ่ง, response static 16KiB, ArduinoJson heap 16KiB, snapshot/candidate ขนาดคงที่ ไม่ใช้ PSRAM; ตรวจ free heap >=75KB และ largest block >=36KB ก่อน request ไม่มี TFT ใน worker; snapshot copy ใน critical section สั้น ๆ
- 25 fixed locations จาก original Thailand polygon; batch ละ 25 (เต็มหน้า), สอง endpoint, refresh ทุกชั่วโมงหลัง success; retry exponential 1–30 นาทีหลัง failure ไม่ publish partial batch, ไม่เขียนข้อมูล API ลง NVS
- `map_decode.h`: ตรวจ array length, numeric/non-null, finite/range, หน่วย, unix timestamp ไม่เก่าเกิน 3h/อนาคตเกิน 30min; ไม่ยอมรับ malformed/oversized response เก็บเวลาตัวอย่างที่เก่าที่สุดเป็น model time
- `map_ui.cpp` / `map_math.h`: IDW inverse squared distance, longitude scale cos(15°), fixed continuous color scale; scanline RGB565 buffer 296 bytes วาด 4 rows/loop, เต็มจอเฉพาะเข้า Home จากหน้าอื่น; ไม่ล้าง status panel ทุกวินาที ใช้ cache ข้อความ/สีรายบรรทัด, redraw map เฉพาะค่า/validity/selection เปลี่ยน ไม่ redraw เมื่อมีแต่ error revision; ไม่มี slide animation แต่เปลี่ยนหน้าแบบ progressive redraw
- `thailand_mask.h`: offline raster 148×230, flash 4,255 bytes, asset/provenance และ licenses ที่ `assets/map/`; pixels นอกประเทศไทยไม่ interpolate เกาะเล็กกว่าพิกเซลอาจหาย
- รอ NTP >=2024 ก่อน HTTPS; ISRG roots X1/X2 ตรวจ chain/hostname/dates ไม่มี setInsecure; SNTP ไม่ authenticated ต้องดูแล trust roots ในอนาคต
- PM2.5 เป็น CAMS Global ~45km ไม่ใช่สถานีวัด ไม่ใช่ AQI; อุณหภูมิเป็นอากาศ 2m ไม่ใช่ surface temperature; interpolation เป็นภาพประมาณไม่เพิ่ม scientific resolution
- API ฟรีเฉพาะ non-commercial, CC BY 4.0, ต้องเครดิต Open-Meteo/CAMS; คิดเผื่อ 1,200 location-calls/day/device ก่อน retry; ดู docs/terms/provenance/TLS ที่ `assets/map/README.md`
- Validation รอบนี้: `pio run -e cyd_ili9341` ผ่าน Flash 1,001,221 / RAM 58,356 bytes; host tests ทั้ง 6 scripts และ stack guard self-test ผ่าน รวม actual worker mock ตรวจ batch retry/backoff และไม่โหลด batch สำเร็จซ้ำ, actual TFT stub ตรวจข้อความเฉพาะตัวเลขเวลา/scale และขอบจอ; `git diff --check` ผ่าน ยังไม่ยืนยัน TLS บนบอร์ดจริง
