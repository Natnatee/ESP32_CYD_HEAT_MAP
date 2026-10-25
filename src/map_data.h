#pragma once
#include <stdint.h>
#include "thailand_mask.h"

namespace map_data {
struct Snapshot {
    float values[thailand::COUNT];
    uint32_t model_time;
    uint32_t received_at;
    uint32_t revision;
    bool valid;
    bool failed;
};
bool begin();
void diagnostics();
bool snapshot(unsigned page, Snapshot &out);
}
