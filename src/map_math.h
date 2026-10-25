#pragma once
#include <math.h>
#include <stdint.h>
#include "thailand_mask.h"

namespace heat_map {
inline float interpolate(float lat, float lon, const float *values) {
    float sum=0, weights=0;
    for (unsigned i=0; i<thailand::COUNT; ++i) {
        if (!isfinite(values[i])) continue;
        float dx=(lon-thailand::LOCATIONS[i].lon)*0.966f;
        float dy=lat-thailand::LOCATIONS[i].lat;
        float d=dx*dx+dy*dy;
        if (d<0.000001f) return values[i];
        float w=1.0f/d;
        sum+=w*values[i]; weights+=w;
    }
    return weights>0 ? sum/weights : NAN;
}
inline uint16_t color(float value, bool pm) {
    if (!isfinite(value)) return 0x4208;
    float t=pm ? value/100.0f : (value-10.0f)/35.0f;
    t=fmaxf(0, fminf(1, t));
    // Continuous blue -> cyan -> yellow -> red. Fixed scale, not AQI categories.
    float r=fminf(1, fmaxf(0, 3*t-1));
    float g=fminf(1, fmaxf(0, fminf(3*t,3-3*t)));
    float b=fminf(1, fmaxf(0, 2-3*t));
    return (uint16_t(r*31)<<11)|(uint16_t(g*63)<<5)|uint16_t(b*31);
}
enum class Gesture { NONE, TAP, LEFT, RIGHT };
inline Gesture gesture(int dx, int dy, int max_move, uint32_t duration) {
    if (duration>1500) return Gesture::NONE;
    if (abs(dx)>=45 && abs(dx)>abs(dy)*2) return dx<0 ? Gesture::LEFT : Gesture::RIGHT;
    if (max_move<=12 && duration<=700) return Gesture::TAP;
    return Gesture::NONE;
}
}
