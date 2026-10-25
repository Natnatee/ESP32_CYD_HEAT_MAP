#pragma once
#include <ArduinoJson.h>
#include <math.h>
#include <string.h>
#include "map_data.h"

namespace map_data {
// Candidate is private to worker: never publish a partially decoded refresh.
inline bool decode_batch(JsonArray array, unsigned page, unsigned start, unsigned count,
                         uint32_t now, Snapshot &out) {
    if (page>1 || !count || start>thailand::COUNT || count>thailand::COUNT-start ||
            array.isNull() || array.size()!=count) return false;
    const char *key=page ? "pm2_5" : "temperature_2m";
    for (unsigned offset=0; offset<count; ++offset) {
        JsonObject obj=array[offset];
        JsonVariant value=obj["current"][key];
        JsonVariant timestamp=obj["current"]["time"];
        if (!value.is<float>() || !timestamp.is<uint32_t>()) return false;
        float v=value.as<float>();
        uint32_t t=timestamp.as<uint32_t>();
        if (!isfinite(v) || v<(page ? 0 : -60) || v>(page ? 5000 : 65) ||
            t<1704067200 || t>now+1800 || now>t+10800) return false;
        const char *unit=obj["current_units"][key] | "";
        if (strcmp(unit,page ? "μg/m³" : "°C")!=0) return false;
        out.values[start+offset]=v;
        if (!out.model_time || t<out.model_time) out.model_time=t;
    }
    return true;
}
}
