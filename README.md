# ESP32 CYD Thailand Heat Map

แผนที่อุณหภูมิอากาศประเทศไทย และหน้า PM2.5 สำหรับ ESP32-2432S028 / HW-458 จอ ILI9341 แนวนอน 320×240 ใช้ TFT_eSPI โดยตรง ไม่ใช้ PSRAM หรือ framebuffer เต็มจอ เป็น prototype ยังไม่ได้ตรวจบนบอร์ดจริง

## การใช้งาน
- เมื่อไม่มี calibration ที่ใช้ได้ ให้แตะจุดกลางวงกลมทั้ง 4 มุม มุมใดก่อนก็ได้ แตะนิ่งแล้วปล่อย บันทึกลง NVS เมื่อ fit ผ่าน; บูตถัดไปข้ามขั้นตอนนี้
- หน้า WiFi มีช่อง SSID/Password และคีย์บอร์ด QWERTY พร้อมตัวเลข/สัญลักษณ์, Space และ Del รองรับ ASCII
- ใช้ WiFi **2.4GHz** บันทึก credentials เฉพาะเมื่อเชื่อมสำเร็จ บูตจะลองค่าที่บันทึกอัตโนมัติหนึ่งครั้ง จำกัด 20 วินาที ยกเลิกด้วย Cancel ได้
- ขั้นตอนตั้งค่าเริ่มต้น: เชื่อมไม่สำเร็จ/หมดเวลา/Cancel จะกลับฟอร์มแก้ไข โดยไม่ลบค่าที่บันทึกไว้
- หลังเข้าแผนที่แล้ว WiFi หลุดจะคงหน้า/ข้อมูลเดิม แสดง `OFFLINE / STALE` (หรือ `OFFLINE / retrying` เมื่อยังไม่มีข้อมูล) และ reconnect แบบไม่บล็อก ครั้งละไม่เกิน 20 วินาที พัก 5/10/20/40/80 วินาที สูงสุด 80 วินาทีต่อรอบ ไม่กลับฟอร์มและไม่เขียน NVS; เชื่อมคืนแล้ว worker ใช้ตาราง refresh/retry เดิม
- หน้า Home เป็นแผนที่ **อุณหภูมิอากาศที่ 2m (°C)** ปัดซ้ายไป **PM2.5 (µg/m³)** ปัดขวากลับอุณหภูมิ ไม่มีแถบปุ่ม `WiFi` / `Calibrate` หรือ hitbox ด้านล่าง ใช้ Serial `w` / `c` เมื่อต้องการตั้งค่าใหม่
- NTP ใช้ `pool.ntp.org` และ `time.google.com` แบบไม่บล็อก UI แสดง placeholder จน epoch >= `1704067200`

## Hardware / Pin Map
มองจากด้านหลัง พอร์ต USB อยู่ด้านบน รูปแสดงตำแหน่งส่วนประกอบโดยประมาณ ไม่ใช่ลำดับขาของคอนเนกเตอร์

```text
       Micro USB     USB-C
    +--------------------------+
    |      ESP32-2432S028       |
    |                          |-- SPEAK (ไม่ใช้)
    | microSD                  |
    | (ไม่ใช้)   TFT ภายใน     |
    |          CLK14 MOSI13    |
    |          MISO12 CS15 DC2 |
    |          BL21 RST=-1     |
    | RGB LED                  |
    | (ไม่ใช้) Touch ภายใน     |
    |          CLK25 MOSI32    |
    |          MISO39 CS33     |
    |          IRQ36          |
    |       ESP32-WROOM   BOOT |
    |       เสาอากาศ      RESET|
    +--------------------------+
```

คงขาเดิม: TFT rotation **3**, touch rotation **1**; affine ใช้พิกัด canonical เดิมแล้วกลับพิกัดก่อนส่ง UI จึงใช้ calibration/NVS เดิมได้ ไม่ต้องลบข้อมูล ขาทัชยังต้องยืนยันบนบอร์ดจริง อ่าน pressure แบบ polling ไม่ใช้ IRQ เป็น gate

ใช้สาย USB ส่งข้อมูลได้ จ่ายไฟผ่าน USB เพียงพอร์ตเดียว GPIO เป็น 3.3V ห้ามป้อน 5V เข้า GPIO

## Build
ติดตั้ง PlatformIO แล้วรันจาก root:

```bash
pio run -e cyd_ili9341
```

`cyd_ili9341` เป็นค่าหลัก; `pio run -e cyd_st7789` มีไว้ตรวจ build compatibility เท่านั้น ไม่ใช่การตรวจพบชนิดจออัตโนมัติ

Dependencies: **TFT_eSPI 2.5.43**, **XPT2046_Touchscreen v1.4**, **ArduinoJson 6.21.5** บน **espressif32 6.9.0**; WiFi, HTTPS, Preferences และ SNTP/time.h มากับ Arduino ESP32

## Serial (115200 baud)
| คำสั่ง | หน้าที่ |
|---|---|
| `c` | ลบเฉพาะ calibration แล้วเริ่มใหม่ ไม่ลบ WiFi |
| `w` | ลบเฉพาะ WiFi ที่บันทึก แล้วกลับฟอร์มเมื่อ calibration พร้อม |
| `t` | เปิด/ปิด touch diagnostics |
| `h` | ดู heap/stack diagnostics |

รองรับเฉพาะ `c/w/t/h` ไม่ log credentials

## NVS / ความปลอดภัย
- Preferences namespace `cyd_settings` แยก record `cal`/`wifi` รูปแบบ version/profile/CRC เดิมยังเข้ากันได้ CRC ตรวจข้อมูลเสีย ไม่ใช่การเข้ารหัส
- Calibration บันทึกเมื่อผ่านการตรวจ; WiFi บันทึกเมื่อเชื่อมสำเร็จและข้อมูลเปลี่ยน ไม่เขียนทับค่าดีเมื่อเชื่อมล้มเหลว/Cancel/หลุด
- **Password มองเห็นบนจอ และ NVS เก็บ plaintext** ไม่เปิด flash/NVS encryption ผู้เข้าถึง flash อาจกู้รหัสได้ `w` ไม่ใช่ secure wipe

## รายการตรวจบนบอร์ด
ตรวจคาลิเบรต/รีบูต, ปุ่มและคีย์บอร์ดริมจอ, saved WiFi autoattempt/Cancel/timeout 20 วินาที, WiFi หลุด/กลับมาแล้วคงแผนที่และ reconnect ตาม backoff, placeholder ก่อน NTP และเวลา UTC+7, ปัดซ้าย/ขวาและแตะบริเวณปุ่มเก่าต้องไม่เปิดตั้งค่า, ภาพ/สีแผนที่, TLS หลัง NTP, API timeout/retry/stale และ heap/stack ระหว่าง HTTPS หลายรอบ

ผลล่าสุด `cyd_ili9341`: **Flash 1,001,793 bytes (76.4%) / static RAM 66,548 bytes (20.3%)**, loop stack frame 224 bytes (ไม่ใช่ peak runtime stack) ผ่าน build และ host tests ด้านล่าง; มี warning `TFT_eSPI TOUCH_CS not defined` ตามเดิม เพราะใช้ XPT2046 แยกบัส ไม่ได้ใช้ TFT_eSPI touch

ตรวจสอบด้วย `pio run -e cyd_ili9341` และ host tests: `python tools/test_ui_network.py`, `python tools/test_heat_map.py`, `python tools/test_map_decode.py`, `python tools/test_touch_mapping.py`, `python tools/test_saved_settings.py`, `python tools/check_stack_frames.py --self-test` ไม่ flash/upload/monitor

## ข้อมูลและข้อจำกัด
- Open-Meteo weather + **CAMS Global model** สำหรับ PM2.5 ไม่ใช่สถานีวัด ไม่ใช่ AQI และไม่ใช่อุณหภูมิพื้นผิว สีใช้สเกลคงที่ 10–45°C / 0–100 µg/m³ (เกินปลายสเกลสีอิ่มตัว) ช่วงตัวเลขแสดง min/max ของจุดตัวอย่าง ไม่ใช่ทุกพิกเซล
- ดึง 25 จุดในประเทศไทยทุก 1 ชั่วโมง รวม 25 จุดเป็นคำขอเดียวต่อหน้า (2 GET ต่อรอบปกติ) ใช้ inverse-distance interpolation ให้สีต่อเนื่องและ clip ขอบเขตจริงจาก **Natural Earth public domain** เกาะเล็กอาจหายตามความละเอียด ไม่เพิ่มความละเอียดทางวิทยาศาสตร์และไม่ใช้เพื่อเตือนภัย/ตัดสินใจสุขภาพ
- **Open-Meteo / Copernicus CAMS / CAMS ENSEMBLE**, ข้อมูล CC BY 4.0; แผนที่ Made with Natural Earth ดู [แหล่งข้อมูล ใบอนุญาต และ API terms](assets/map/README.md)
- API ฟรีใช้ **ไม่เชิงพาณิชย์เท่านั้น** ไม่ต้องใช้ key คิดเผื่อแบบ location-call ประมาณ 1,200/day/เครื่องก่อน retry; เครื่องหลายตัว/IP ร่วมอาจชน rate limit ส่งเฉพาะพิกัดตัวอย่างสาธารณะ ผู้ให้บริการเห็น public IP
- HTTPS ตรวจ CA/hostname/date ด้วย ISRG Root X1/X2 รอ NTP ก่อนเรียก ไม่มี insecure fallback; เครือข่ายทำใน worker ไม่เรียก TFT จาก worker
- Connect/read timeout 8 วินาที, TLS handshake 20 วินาที, จำกัดอ่าน body 15 วินาที/16KiB; retry 1/2/4/8/16/30 นาที ข้อมูลเก็บใน RAM เฉพาะรอบที่ครบและผ่าน validation แต่ละหน้าอิสระ ล้มเหลวคงข้อมูลเก่าพร้อม `STALE / retrying`; แสดง `STALE / retrying` เมื่อ model/การรับข้อมูลเกิน 2 ชั่วโมง รีบูตต้องโหลดใหม่
- วาดเต็มจอเฉพาะเข้าจากหน้าตั้งค่า; เปลี่ยนหน้าแผนที่วาดเฉพาะ title/legend/status/map, idle ไม่วาดแผนที่ซ้ำ สถานะวาดเฉพาะบรรทัดที่ข้อความ/สีเปลี่ยน ไม่ล้าง panel ทุกวินาที และ error revision ที่ไม่มีค่าใหม่ไม่เริ่มวาด map ซ้ำ
- ก่อนมีข้อมูลแสดงแผนที่เทา `Loading` และ `Data --:--`; NTP ไม่สำเร็จจะไม่เรียก API และเวลาเครื่องเป็น `Now --:--:--` วันที่/เวลาข้อมูลเป็น UTC+7 ไม่มีการแสดงข้อมูลตัวอย่างปลอม

## Faster fetch / information panel (2026-10-26)
- ตัด diagnostic DNS/TLS probe ให้ HTTPClient จัดการ HTTPS เพียงทางเดียว คงตรวจ CA/hostname/date; อ่าน TLS lastError เฉพาะ transport failure ไม่พิมพ์ error เก่าหลัง success
- ปกติ **2 GET / 2 TLS connections** ต่อ refresh (เดิม 10 GET + 10 probe connections); publish อุณหภูมิครบ 25 จุดก่อนเริ่ม PM2.5 ไม่ publish partial คง retry/backoff/idle-priority worker
- คงแผนที่ซ้ายขนาดใหญ่ 148×230; แผงขวา ASCII แสดง Temperature / Air at 2 m / Celsius หรือ PM2.5 / CAMS Global / ug/m3 (not AQI)
- `Now` = เวลาท้องถิ่น; `Data dd/mm HH:MM` = timestamp ที่เก่าที่สุดของ model 25 จุด ทั้งคู่ Bangkok UTC+7; `Fetched N m ago` = อายุหลังรับชุดครบ ไม่ใช่เวลารัน model; Min/Max เป็นค่าจุดตัวอย่าง หน่วยตามชื่อหน้า
- Body คงที่ 16KiB + JSON heap 16KiB ปฏิเสธเกินขนาด/ขาด/decoder fail ไม่มี PSRAM; ต้องวัด TLS duration และ minimum heap บนบอร์ดก่อนสรุปความเร็วจริง
- เพิ่ม `python tools/test_network_fetch.py` รัน actual fetch กับ network mock ตรวจ TLS ครั้งเดียว/25 จุด/body bounds/failure ไม่ใช่ทดสอบ TLS จริงบน ESP32
- Validation 2026-10-26: build ILI9341 และ ST7789 compatibility ผ่าน, host tests ทั้ง 7 scripts + stack guard self-test ผ่าน, `git diff --check` ผ่าน; warning TOUCH_CS เดิม ไม่มี upload/flash/monitor/commit

## Fonts / License
UI ใช้ **Nunito Bold** จาก Google Fonts ภายใต้ **SIL Open Font License 1.1** ดู `assets/fonts/OFL.txt` และต้นฉบับ `assets/fonts/Nunito.ttf` ฝัง ASCII bitmap 18/26px ใน `src/ui_fonts.h` ไม่ดาวน์โหลดขณะรัน

สร้างฟอนต์ใหม่ด้วย `python tools/generate_ui_fonts.py` (ต้องมี Pillow เฉพาะขั้นตอนสร้างฟอนต์ ไม่ใช่ dependency ของ firmware build)
- Validation รอบก่อน: `pio run -e cyd_ili9341` ผ่าน Flash 1,001,221 / RAM 58,356 bytes; host tests ทั้ง 6 scripts และ stack guard self-test ผ่าน รวม actual worker mock ตรวจ batch retry/backoff และไม่โหลด batch สำเร็จซ้ำ, actual TFT stub ตรวจข้อความเฉพาะตัวเลขเวลา/scale และขอบจอ; `git diff --check` ผ่าน ยังไม่ยืนยัน TLS บนบอร์ดจริง
