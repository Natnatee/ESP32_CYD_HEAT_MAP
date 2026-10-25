"""Exercise firmware JSON decoder with installed pinned ArduinoJson, offline.
Run pio run -e cyd_ili9341 first to install headers. Requires Python/g++ only.
"""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
headers=list((ROOT/'.pio/libdeps').glob('cyd_ili9341/ArduinoJson/src/ArduinoJson.h'))
assert headers, 'Run pio run -e cyd_ili9341 first'
source=r'''
#include "map_decode.h"
#include <cassert>
#include <cstdio>
#include <string>
int main() {
    DynamicJsonDocument doc(8192);
    map_data::Snapshot out{};
    const uint32_t now=1792944900;
    const char *weather=R"JSON([{"current":{"time":1792944900,"temperature_2m":26.2},"current_units":{"temperature_2m":"°C"}}])JSON";
    assert(!deserializeJson(doc,weather));
    assert(map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    assert(fabsf(out.values[0]-26.2)<.001 && out.model_time==now);
    assert(!out.valid); // Only worker may publish a complete candidate.
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,2,now,out));
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,thailand::COUNT,1,now,out));
    assert(!map_data::decode_batch(doc.as<JsonArray>(),1,0,1,now,out));
    doc[0]["current"]["temperature_2m"]=nullptr;
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    doc[0]["current"]["temperature_2m"]="26.2";
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    doc[0]["current"]["temperature_2m"]=100;
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    doc[0]["current"]["temperature_2m"]=25;
    doc[0]["current_units"]["temperature_2m"]="F";
    assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    doc[0]["current_units"]["temperature_2m"]="°C";
    for (uint32_t invalid:{0u,now-10801,now+1801}) {
        doc[0]["current"]["time"]=invalid;
        assert(!map_data::decode_batch(doc.as<JsonArray>(),0,0,1,now,out));
    }
    const char *pm=R"JSON([{"current":{"time":1792944000,"pm2_5":12.4},"current_units":{"pm2_5":"μg/m³"}}])JSON";
    assert(!deserializeJson(doc,pm));
    out=map_data::Snapshot{};
    assert(map_data::decode_batch(doc.as<JsonArray>(),1,0,1,now,out));
    assert(out.model_time==1792944000 && fabsf(out.values[0]-12.4)<.001);
    doc[0]["current"]["pm2_5"]=-1;
    assert(!map_data::decode_batch(doc.as<JsonArray>(),1,0,1,now,out));
    assert(deserializeJson(doc,"[{broken"));
    assert(!deserializeJson(doc,"{\"error\":true}"));
    assert(!map_data::decode_batch(doc.as<JsonArray>(),1,0,1,now,out));
    // Same bounded, mutable response and document capacities as firmware.
    char response[16384];
    DynamicJsonDocument full(16384);
    for (unsigned page=0; page<2; ++page) {
        std::string payload="[";
        for (unsigned i=0; i<thailand::COUNT; ++i) {
            if (i) payload+=',';
            payload+=page ? pm+1 : weather+1;
            payload.pop_back(); // Strip array closing bracket, retain object.
        }
        payload+=']';
        assert(payload.size()<sizeof(response));
        memcpy(response,payload.c_str(),payload.size()+1);
        assert(!deserializeJson(full,response,payload.size(),DeserializationOption::NestingLimit(6)));
        out=map_data::Snapshot{};
        assert(map_data::decode_batch(full.as<JsonArray>(),page,0,thailand::COUNT,now,out));
        assert(!out.valid && out.values[thailand::COUNT-1]>0);
        assert(!map_data::decode_batch(full.as<JsonArray>(),page,~0u,2,now,out));
        assert(!map_data::decode_batch(full.as<JsonArray>(),page,0,0,now,out));
        full[thailand::COUNT-1]["current"][page ? "pm2_5" : "temperature_2m"]=nullptr;
        assert(!map_data::decode_batch(full.as<JsonArray>(),page,0,thailand::COUNT,now,out));
    }
    std::string oversized(20000,'[');
    assert(deserializeJson(full,oversized.c_str(),DeserializationOption::NestingLimit(6)));
    puts("PASS: full 25-point bounded decoder, numeric/null/unit/range/time/length/bounds/errors");
}
'''
with tempfile.TemporaryDirectory(prefix='cyd-decode-') as folder:
    folder=Path(folder)
    (folder/'test.cpp').write_text(source,encoding='utf-8')
    subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I',str(ROOT/'src'),'-I',str(headers[0].parent),str(folder/'test.cpp'),'-o',str(folder/'test.exe')],check=True,timeout=45)
    subprocess.run([str(folder/'test.exe')],check=True,timeout=10)
