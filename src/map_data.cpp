#include "map_data.h"
#include "map_decode.h"
#include "api_roots.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WiFi.h>
#include <time.h>
#include <math.h>
#include <esp_heap_caps.h>

// Equal-priority idle tasks must receive tick-driven CPU time even while TLS
// performs CPU-bound work inside a single library call. yield() at priority 1
// cannot schedule idle; pinning to the other core only relocates starvation.
#if configUSE_PREEMPTION != 1 || configUSE_TIME_SLICING != 1 || configIDLE_SHOULD_YIELD != 0
#error "Map TLS worker requires preemption, time slicing and non-yielding idle tasks"
#endif

namespace map_data {
namespace {
constexpr uint32_t REFRESH_MS=3600000;
constexpr unsigned BATCH=thailand::COUNT; // One bounded response per page (25 locations).
Snapshot published[2]{};
portMUX_TYPE lock=portMUX_INITIALIZER_UNLOCKED;
TaskHandle_t worker_handle=nullptr;
// Single worker owns all network/parser buffers; no full response String or framebuffer.
char response[16384];
Snapshot candidate[2]{};

bool fetch_batch(unsigned page, unsigned start, DynamicJsonDocument &doc) {
    if (WiFi.status()!=WL_CONNECTED || ESP.getFreeHeap()<75000 ||
        heap_caps_get_largest_free_block(MALLOC_CAP_8BIT)<36000) return false;
    String url=page ? "https://air-quality-api.open-meteo.com/v1/air-quality?" :
                      "https://api.open-meteo.com/v1/forecast?";
    unsigned end=min(start+BATCH, thailand::COUNT);
    url += "latitude=";
    for (unsigned i=start; i<end; ++i) {
        if (i!=start) url+=',';
        url+=String(thailand::LOCATIONS[i].lat,3);
    }
    url += "&longitude=";
    for (unsigned i=start; i<end; ++i) {
        if (i!=start) url+=',';
        url+=String(thailand::LOCATIONS[i].lon,3);
    }
    url+=page ? "&current=pm2_5&domains=cams_global" : "&current=temperature_2m&temperature_unit=celsius";
    url+="&timeformat=unixtime&timezone=GMT&forecast_days=1";
    WiFiClientSecure tls;
    tls.setCACert(API_ROOTS); // Hostname, chain and certificate dates checked by mbedTLS.
    tls.setHandshakeTimeout(20);
    tls.setTimeout(8); // WiFiClientSecure uses seconds, unlike HTTPClient milliseconds.
    HTTPClient http;
    http.useHTTP10(true); // No chunked transfer encoding in the bounded response reader.
    http.setConnectTimeout(8000);
    http.setTimeout(8000);
    http.setReuse(false);
    if (!http.begin(tls,url)) return false;
    http.addHeader("Accept-Encoding","identity");
    uint32_t phase_started=millis();
    Serial.printf("Map GET begin page=%u batch=%u core=%d heap=%u stack-min=%u\n",page,start,xPortGetCoreID(),ESP.getFreeHeap(),unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    int status=http.GET();
    Serial.printf("Map GET end page=%u batch=%u ms=%lu HTTP=%d stack-min=%u\n",page,start,static_cast<unsigned long>(millis()-phase_started),status,unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    if (status<0) {
        char error[160]{};
        int tls_error=tls.lastError(error,sizeof(error));
        Serial.printf("Map TLS failure error=%d detail=%.159s\n",tls_error,error);
    }
    if (status!=200) Serial.printf("Map API page=%u HTTP=%d (TLS/network errors fail closed)\n",page,status);
    int expected=http.getSize();
    bool ok=status==200 && expected<int(sizeof(response));
    size_t used=0;
    uint32_t started=millis();
    WiFiClient *stream=http.getStreamPtr();
    while (ok && (http.connected() || stream->available()) &&
           (expected<0 || used<size_t(expected))) {
        if (millis()-started>15000 || WiFi.status()!=WL_CONNECTED) { ok=false; break; }
        int available=stream->available();
        if (!available) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
        if (used>=sizeof(response)-1) { ok=false; break; }
        size_t n=stream->readBytes(response+used,min(size_t(available),sizeof(response)-1-used));
        used+=n;
    }
    http.end();
    Serial.printf("Map body end page=%u batch=%u ms=%lu bytes=%u ok=%d stack-min=%u\n",page,start,static_cast<unsigned long>(millis()-started),unsigned(used),ok,unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    if (!ok || (expected>=0 && used!=size_t(expected))) return false;
    response[used]=0;
    doc.clear();
    phase_started=millis();
    if (start==0) candidate[page]=Snapshot{};
    bool decoded=!deserializeJson(doc,response,used,DeserializationOption::NestingLimit(6)) &&
        decode_batch(doc.as<JsonArray>(),page,start,end-start,uint32_t(time(nullptr)),candidate[page]);
    Serial.printf("Map decode end page=%u batch=%u ms=%lu ok=%d stack-min=%u\n",page,start,static_cast<unsigned long>(millis()-phase_started),decoded,unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    return decoded;
}
void worker(void *) {
    DynamicJsonDocument doc(16384);
    uint32_t next[2]={0,0};
    unsigned failures[2]={0,0}, batch[2]={0,0}, attempts[2]={0,0};
    for (;;) {
        if (WiFi.status()==WL_CONNECTED && time(nullptr)>=1704067200) {
            for (unsigned page=0; page<2; ++page) {
                if (int32_t(millis()-next[page])<0) continue;
                bool ok=doc.capacity()!=0 && fetch_batch(page,batch[page],doc);
                if (ok) {
                    attempts[page]=0;
                    batch[page]+=BATCH;
                    if (batch[page]<thailand::COUNT) {
                        next[page]=millis()+150;
                        continue;
                    }
                    candidate[page].valid=true;
                    candidate[page].received_at=millis();
                    portENTER_CRITICAL(&lock);
                    candidate[page].revision=published[page].revision+1;
                    published[page]=candidate[page];
                    portEXIT_CRITICAL(&lock);
                    failures[page]=0;
                    batch[page]=0;
                    candidate[page]=Snapshot{};
                    next[page]=millis()+REFRESH_MS;
                } else {
                    portENTER_CRITICAL(&lock);
                    published[page].failed=true;
                    ++published[page].revision;
                    portEXIT_CRITICAL(&lock);
                    // Two local retries; other page gets a turn during backoff.
                    if (++attempts[page]<3) {
                        next[page]=millis()+1000u*attempts[page];
                    } else {
                        attempts[page]=0;
                        failures[page]=min(failures[page]+1,6u);
                        next[page]=millis()+min(60000u<<(failures[page]-1),1800000u);
                        // Retain successful batches, but never mix indefinitely old samples.
                        if (candidate[page].model_time &&
                            time(nullptr)>time_t(candidate[page].model_time)+7200) {
                            batch[page]=0;
                            candidate[page]=Snapshot{};
                        }
                    }
                    Serial.printf("Map retry page=%u batch=%u wait-ms=%lu\n",page,batch[page],
                        static_cast<unsigned long>(next[page]-millis()));
                }
                vTaskDelay(pdMS_TO_TICKS(150));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
}
bool begin() {
    if (worker_handle) return true;
    return xTaskCreate(worker,"map_network",12288,nullptr,tskIDLE_PRIORITY,&worker_handle)==pdPASS;
}
void diagnostics() {
    if (worker_handle) Serial.printf("Map worker stack-min-free=%u bytes\n",unsigned(uxTaskGetStackHighWaterMark(worker_handle)));
    else Serial.println("Map worker not started");
}
bool snapshot(unsigned page, Snapshot &out) {
    if (page>1) return false;
    portENTER_CRITICAL(&lock);
    out=published[page];
    portEXIT_CRITICAL(&lock);
    return out.valid;
}
}
