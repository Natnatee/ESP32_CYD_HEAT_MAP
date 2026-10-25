#include "map_ui.h"
#include "map_data.h"
#include "map_math.h"
#include <time.h>
#include <stdio.h>
#include <WiFi.h>
#include <string.h>

namespace map_ui {
namespace {
unsigned page=0;
int row=thailand::HEIGHT;
uint32_t last_status=0;
map_data::Snapshot data{};
uint16_t pixels[thailand::WIDTH];
bool worker_ok=false, worker_started=false;
char labels[12][64]{};
unsigned label_index=0;
void text(TFT_eSPI &tft, const char *s, int x, int y, uint16_t color=TFT_WHITE) {
    unsigned index=label_index++;
    char key[64];
    snprintf(key,sizeof(key),"%u:%s",unsigned(color),s);
    if (index<12 && strcmp(labels[index],key)==0) return;
    if (index<12) snprintf(labels[index],sizeof(labels[index]),"%s",key);
    tft.fillRect(x,y,320-x,8,TFT_BLACK);
    tft.setTextColor(color,TFT_BLACK);
    tft.drawString(s,x,y,1);
}
void status(TFT_eSPI &tft) {
    label_index=0;
    time_t now=time(nullptr);
    tm local{};
    char label[48];
    const bool online=WiFi.status()==WL_CONNECTED;
    const bool stale=data.valid && (data.failed || now>time_t(data.model_time)+7200 ||
        millis()-data.received_at>7200000);
    text(tft,page ? "PM2.5" : "Temperature",190,12,TFT_CYAN);
    text(tft,page ? "CAMS Global" : "Air at 2 m",190,28);
    text(tft,page ? "ug/m3 (not AQI)" : "Celsius (C)",190,40);
    if (now>=1704067200) {
        localtime_r(&now,&local);
        strftime(label,sizeof(label),"Now %H:%M:%S",&local);
    } else snprintf(label,sizeof(label),"Now --:--:--");
    text(tft,label,190,64);
    if (data.valid) {
        time_t model=data.model_time;
        localtime_r(&model,&local);
        strftime(label,sizeof(label),"Data %d/%m %H:%M",&local);
    } else snprintf(label,sizeof(label),"Data --:--");
    text(tft,label,190,80);
    text(tft,"Bangkok UTC+7",190,92);
    if (data.valid) snprintf(label,sizeof(label),"Fetched %lu m ago",
        static_cast<unsigned long>((millis()-data.received_at)/60000));
    else snprintf(label,sizeof(label),"Waiting for data");
    text(tft,label,190,112);
    float low=data.values[0], high=low;
    for (unsigned i=1; i<thailand::COUNT; ++i) {
        if (data.values[i]<low) low=data.values[i];
        if (data.values[i]>high) high=data.values[i];
    }
    if (data.valid) snprintf(label,sizeof(label),"Min %.1f",low);
    else snprintf(label,sizeof(label),"Min --");
    text(tft,label,190,132);
    if (data.valid) snprintf(label,sizeof(label),"Max %.1f",high);
    else snprintf(label,sizeof(label),"Max --");
    text(tft,label,190,144);
    text(tft,!online ? (data.valid ? "OFFLINE / STALE" : "OFFLINE / retrying") :
        !worker_ok ? "Worker unavailable" : !data.valid ? (data.failed ? "Retrying" : "Loading") :
        stale ? "STALE / retrying" : "25 model points",190,164,TFT_YELLOW);
    text(tft,page ? "Open-Meteo / CAMS" : "Open-Meteo",190,184);

}
void frame(TFT_eSPI &tft) {
    memset(labels,0,sizeof(labels));
    tft.fillRect(190,0,130,240,TFT_BLACK);
    tft.setSwapBytes(true);
    tft.setFreeFont(nullptr);
    tft.setTextDatum(TL_DATUM);
    tft.setTextSize(1);
    tft.setTextColor(TFT_WHITE,TFT_BLACK);
    for (int i=0; i<110; ++i)
        tft.drawFastVLine(200+i,210,10,heat_map::color(page ? i*100.f/109 : 10+i*35.f/109,page));
    tft.drawString(page ? "0     50    100" : "10   27.5    45",200,226,1);
    map_data::snapshot(page,data);
    row=0;
    status(tft);
    last_status=millis();
}
}
void enter(TFT_eSPI &tft) {
    if (!worker_started) { worker_ok=map_data::begin(); worker_started=worker_ok; }
    tft.fillScreen(TFT_BLACK); // Only on entry from another screen, never in tick().
    frame(tft);
}
void swipe(TFT_eSPI &tft, bool left) {
    unsigned next=left ? 1 : 0;
    if (next!=page) { page=next; frame(tft); }
}
void tick(TFT_eSPI &tft) {
    if (row<thailand::HEIGHT) {
        // Four scanlines per loop; touch/WiFi gate runs between slices.
        for (int stop=min(row+4,thailand::HEIGHT); row<stop; ++row) {
            float lat=thailand::NORTH-(row+.5f)*(thailand::NORTH-thailand::SOUTH)/thailand::HEIGHT;
            for (int x=0; x<thailand::WIDTH; ++x) {
                pixels[x]=TFT_BLACK;
                if (thailand::contains_pixel(x,row)) {
                    float lon=thailand::WEST+(x+.5f)*(thailand::EAST-thailand::WEST)/thailand::WIDTH;
                    pixels[x]=data.valid ? heat_map::color(heat_map::interpolate(lat,lon,data.values),page) : 0x4208;
                }
            }
            tft.pushImage(30,5+row,thailand::WIDTH,1,pixels);
        }
    }
    if (millis()-last_status>=1000) {
        last_status=millis();
        static map_data::Snapshot next;
        map_data::snapshot(page,next);
        if (next.revision!=data.revision) {
            bool changed=next.valid!=data.valid || memcmp(next.values,data.values,sizeof(data.values))!=0;
            data=next;
            if (changed) row=0;
        }
        status(tft);
    }
}
}
