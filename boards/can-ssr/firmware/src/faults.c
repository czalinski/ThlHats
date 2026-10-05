#include "faults.h"
#include "config.h"
#include "sampling.h"

volatile uint16_t g_faults;
uint8_t g_warnings;
uint8_t g_first_fault = 0xFF;

void fault_raise(uint16_t f)
{
    if ((g_faults & f) == f) return;
    if (g_faults == 0) {
        uint8_t n = 0;
        while (!(f & 1u)) { f >>= 1; n++; }
        g_first_fault = n;
        f <<= n;
        capture_freeze_after(CAPTURE_POST_MS);
    }
    g_faults |= f;
}

uint8_t fault_clear(void)
{
    g_faults = 0;
    g_first_fault = 0xFF;
    capture_rearm();
    return 1;
}
