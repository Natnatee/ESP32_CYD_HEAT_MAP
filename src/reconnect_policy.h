#pragma once
#include <stdint.h>

// Each attempt is bounded; exhaustion waits before a new attempt, never opens setup.
struct ReconnectPolicy {
    bool active=false;
    bool waiting=false;
    uint32_t since=0;
    uint32_t wait_ms=0;
    unsigned failures=0;
    enum Action { NONE, START, STOP };
    void reset() { active=waiting=false; failures=0; }
    Action tick(uint32_t now, bool connected) {
        if (connected) { reset(); return NONE; }
        if (active) {
            if (uint32_t(now-since)<20000) return NONE;
            active=false; waiting=true; since=now;
            if (failures<5) ++failures;
            wait_ms=5000u<<(failures-1);
            return STOP;
        }
        if (waiting && uint32_t(now-since)<wait_ms) return NONE;
        active=true; waiting=false; since=now;
        return START;
    }
};
