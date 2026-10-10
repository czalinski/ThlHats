#include <xc.h>
#include "board.h"
#include "settings.h"
#include "i2c.h"
#include "io.h"

#define CLR 1u
#define SET 2u

typedef struct {
    volatile uint32_t *tris, *port, *lat, *cnpu, *cnpd;
    uint32_t mask;
} pin_t;

#define PIN(P, n) { &TRIS##P, &PORT##P, &LAT##P, &CNPU##P, &CNPD##P, 1u << (n) }

static const pin_t rly_pin[IO_RELAYS] = { PIN(B, 15), PIN(G, 6), PIN(G, 9), PIN(A, 12) };
static const pin_t gpio_pin[IO_GPIOS] = { PIN(A, 11), PIN(A, 0), PIN(B, 11), PIN(B, 12) };
/* AI legs: 1P, 1N, 2P, 2N */
static const pin_t ai_pin[4] = { PIN(E, 12), PIN(E, 13), PIN(C, 11), PIN(C, 2) };
static const uint8_t ai_an[4] = { 12, 13, 11, 8 };
#define AN_VMID     25u
#define DAC_ADDR    0x60u               /* MCP4728, address bits 000 */

#define AVDD_MV     3300
#define OVER_LO     16                  /* counts from either rail = over range */
#define OVER_HI     (4095 - 16)
#define SAMPLES     64
/* leg divider 10M / 130k: Vleg = (Vpin - VMID) * (10M + 130k) / 130k */
#define DIV_NUM     10130
#define DIV_DEN     130

static bool present, ao_present;
static uint16_t ao_code[IO_AOS];
static uint32_t ao_timeout[IO_AOS], ao_t0[IO_AOS];
static bool ao_expired[IO_AOS];
static uint32_t rly_timeout[IO_RELAYS], rly_t0[IO_RELAYS];
static bool rly_expired[IO_RELAYS];
static gpio_mode g_mode[IO_GPIOS];
static gpio_pull g_pull[IO_GPIOS];

/* ------------------------------------------------------------------ ADC */

static void adc_init(void)
{
    /* DS60001519D 25.1 activation sequence */
    ADC0CFG = DEVADC0;
    ADC1CFG = DEVADC1;
    ADC2CFG = DEVADC2;
    ADC3CFG = DEVADC3;
    ADC4CFG = DEVADC4;
    ADC5CFG = DEVADC5;
    ADC7CFG = DEVADC7;

    ADCCON1 = 3u << 21;                     /* SELRES: ADC7 12 bit; ON = 0 */
    /* TQ = 2 / SYSCLK = 16.7 ns; ADC7 TAD = 6 TQ = 100 ns; sample (48 + 2) TAD = 5 us */
    ADCCON2 = (48u << 16) | 3u;
    ADCANCON = 0xAu << 24;                  /* WKUPCLKCNT */
    ADCCON3 = (0u << 30) | (1u << 24) | (0u << 13);     /* SYSCLK, CONCLKDIV 2, AVDD/AVSS */
    ADCIMCON1 = 0;
    ADCIMCON2 = 0;
    ADCIMCON3 = 0;
    ADCTRGMODE = 0;

    ADCANCONSET = _ADCANCON_ANEN7_MASK;
    ADCCON1SET = _ADCCON1_ON_MASK;
    uint32_t t0 = ticks();
    while (!(ADCCON2 & _ADCCON2_BGVRRDY_MASK) || !(ADCANCON & _ADCANCON_WKRDY7_MASK))
        if (ms_since(t0) > 10u)
            break;
    ADCCON3SET = _ADCCON3_DIGEN7_MASK;
}

/* one software-requested conversion on the shared ADC7 */
static uint16_t adc_read(uint8_t an)
{
    volatile uint32_t *data = &ADCDATA0 + 4u * an;     /* ADCDATAn every 0x10 bytes */
    (void)*data;                                        /* clear a stale ready flag */
    ADCCON3 = (ADCCON3 & ~_ADCCON3_ADINSEL_MASK) | an;
    ADCCON3SET = _ADCCON3_RQCNVRT_MASK;
    uint32_t t0 = ticks();
    volatile uint32_t *dstat = an < 32u ? &ADCDSTAT1 : &ADCDSTAT2;
    while (!(*dstat & (1u << (an & 31u))))
        if (ticks() - t0 > CORETIMER_HZ / 1000u)
            return 0;
    return (uint16_t)*data;
}

static int32_t counts_to_mv(int32_t c)
{
    return c * AVDD_MV / 4096;
}

uint16_t io_vmid_mv(void)
{
    uint32_t s = 0;
    for (int k = 0; k < 16; k++)
        s += adc_read(AN_VMID);
    return (uint16_t)counts_to_mv((int32_t)(s / 16u));
}

/* ------------------------------------------------------------------ OA5: VMID */

static void vmid_init(void)
{
    PMD2CLR = _PMD2_OPA5MD_MASK;
    /* low-power unity-gain follower (Table 27-1): ENPGA = 1, OPLPWR = 1, then OPAON */
    CM5CON = _CM5CON_ENPGA_MASK | (1u << 12);
    CM5CONSET = _CM5CON_OPAON_MASK;
}

/* ------------------------------------------------------------------ detection */

/* With the card, every AI leg sits on 100 nF to VMID (and 130k): a 20 us pull-up
 * or pull-down barely moves it. Without it the pin floats and swings rail to rail. */
bool io_detect(void)
{
    int held = 0;
    for (int i = 0; i < 4; i++) {
        const pin_t *p = &ai_pin[i];
        p->cnpu[SET] = p->mask;
        delay_us(20);
        int32_t up = adc_read(ai_an[i]);
        p->cnpu[CLR] = p->mask;
        p->cnpd[SET] = p->mask;
        delay_us(20);
        int32_t down = adc_read(ai_an[i]);
        p->cnpd[CLR] = p->mask;
        if (up - down < 1000)
            held++;
    }
    present = held >= 3;
    ao_present = i2c_probe(DAC_ADDR);
    return present;
}

bool io_present(void)
{
    return present;
}

bool io_ao_present(void)
{
    return ao_present;
}

/* ------------------------------------------------------------------ relays, GPIO */

static void relay_out(uint8_t i, bool on)
{
    const pin_t *p = &rly_pin[i];
    if (on)
        p->lat[SET] = p->mask;
    else
        p->lat[CLR] = p->mask;
}

void io_relay_set(uint8_t n, bool on, uint32_t timeout_ms)
{
    uint8_t i = n - 1u;
    rly_timeout[i] = on ? timeout_ms : 0;
    rly_t0[i] = millis();
    rly_expired[i] = false;
    relay_out(i, on);
}

uint32_t io_relay_timeout(uint8_t n)
{
    return rly_timeout[n - 1u];
}

bool io_relay_expired(uint8_t n)
{
    return rly_expired[n - 1u];
}

static bool ao_out(uint8_t i, uint16_t code);

void io_poll(void)
{
    uint32_t now = millis();
    for (uint8_t i = 0; i < IO_RELAYS; i++)
        if (rly_timeout[i] && now - rly_t0[i] >= rly_timeout[i]) {
            relay_out(i, false);
            rly_timeout[i] = 0;
            rly_expired[i] = true;
        }
    for (uint8_t i = 0; i < IO_AOS; i++)
        if (ao_timeout[i] && now - ao_t0[i] >= ao_timeout[i]) {
            if (!ao_out(i, 0))
                ao_present = false;     /* shows as ao=0; IO SCAN probes again */
            ao_timeout[i] = 0;
            ao_expired[i] = true;
        }
}

bool io_relay_get(uint8_t n)
{
    const pin_t *p = &rly_pin[n - 1u];
    return (*p->lat & p->mask) != 0;
}

void io_gpio_config(uint8_t n, gpio_mode mode, gpio_pull pull, bool out)
{
    uint8_t i = n - 1u;
    const pin_t *p = &gpio_pin[i];
    if (out)
        p->lat[SET] = p->mask;
    else
        p->lat[CLR] = p->mask;
    if (pull == PULL_UP) p->cnpu[SET] = p->mask; else p->cnpu[CLR] = p->mask;
    if (pull == PULL_DOWN) p->cnpd[SET] = p->mask; else p->cnpd[CLR] = p->mask;
    if (mode == GPIO_OUT)
        p->tris[CLR] = p->mask;
    else
        p->tris[SET] = p->mask;
    g_mode[i] = mode;
    g_pull[i] = pull;
}

void io_gpio_get(uint8_t n, gpio_mode *mode, gpio_pull *pull, bool *out, bool *level)
{
    uint8_t i = n - 1u;
    const pin_t *p = &gpio_pin[i];
    *mode = g_mode[i];
    *pull = g_pull[i];
    *out = (*p->lat & p->mask) != 0;
    *level = (*p->port & p->mask) != 0;
}

/* ------------------------------------------------------------------ analog in */

static void ai_raw(uint8_t n, int32_t *p, int32_t *q, int32_t *vmid, bool *over)
{
    uint8_t ap = ai_an[2u * (n - 1u)], aq = ai_an[2u * (n - 1u) + 1u];
    int32_t sp = 0, sq = 0;
    *over = false;
    for (int k = 0; k < SAMPLES; k++) {
        int32_t a = adc_read(ap), b = adc_read(aq);
        if (a < OVER_LO || a > OVER_HI || b < OVER_LO || b > OVER_HI)
            *over = true;
        sp += a;
        sq += b;
    }
    *p = sp;                            /* sums of SAMPLES counts */
    *q = sq;
    int32_t sv = 0;
    for (int k = 0; k < 16; k++)
        sv += adc_read(AN_VMID);
    *vmid = sv * (SAMPLES / 16);
}

/* counts summed over SAMPLES -> mV at the terminal */
static int32_t sum_to_leg_mv(int32_t sum)
{
    int64_t mv = (int64_t)sum * AVDD_MV * DIV_NUM / ((int64_t)4096 * SAMPLES * DIV_DEN);
    return (int32_t)mv;
}

void io_ai_read(uint8_t n, ai_reading *r)
{
    int32_t p, q, v;
    ai_raw(n, &p, &q, &v, &r->over);
    int32_t zero = settings.ai_zero[n - 1u];        /* in summed counts */
    r->diff_mv = sum_to_leg_mv(p - q - zero);
    r->p_mv = sum_to_leg_mv(p - v);
    r->n_mv = sum_to_leg_mv(q - v);
}

int16_t io_ai_zero(uint8_t n)
{
    int32_t p, q, v;
    bool over;
    ai_raw(n, &p, &q, &v, &over);
    int32_t z = p - q;
    if (z > 32767) z = 32767;
    if (z < -32768) z = -32768;
    settings.ai_zero[n - 1u] = (int16_t)z;
    return (int16_t)z;
}

/* ------------------------------------------------------------------ analog out */

/* MCP4728 Multi-Write (DS22187E 5.6.2): 0 1 0 0 0 DAC1 DAC0 UDAC, then
 * VREF PD1 PD0 Gx D11-D8, D7-D0. Internal 2.048 V reference x 2 = 4.096 V
 * full scale (1 mV per code), then x 2.5 on the card: 2.5 mV per code.
 * UDAC = 0 (and ~LDAC tied low): the output follows at the end of the write.
 * Input registers only; the EEPROM keeps its factory 0 V power-up state. */
static bool ao_out(uint8_t i, uint16_t code)
{
    uint8_t b[3] = { (uint8_t)(0x40u | (i << 1)), (uint8_t)(0x90u | (code >> 8)), (uint8_t)code };
    if (!i2c_write(DAC_ADDR, b, 3))
        return false;
    ao_code[i] = code;
    return true;
}

bool io_ao_set(uint8_t n, uint32_t mv, uint32_t timeout_ms)
{
    uint8_t i = n - 1u;
    uint16_t code = (uint16_t)((mv * 2u + 2u) / 5u);   /* mV / 2.5, rounded */
    if (!ao_out(i, code))
        return false;
    ao_timeout[i] = code ? timeout_ms : 0;
    ao_t0[i] = millis();
    ao_expired[i] = false;
    return true;
}

uint32_t io_ao_get(uint8_t n)
{
    return ao_code[n - 1u] * 5u / 2u;
}

uint32_t io_ao_timeout(uint8_t n)
{
    return ao_timeout[n - 1u];
}

bool io_ao_expired(uint8_t n)
{
    return ao_expired[n - 1u];
}

/* ------------------------------------------------------------------ init */

void io_init(void)
{
    for (uint8_t n = 1; n <= IO_RELAYS; n++) {
        const pin_t *p = &rly_pin[n - 1u];
        p->lat[CLR] = p->mask;          /* all outputs off */
        p->cnpd[CLR] = p->mask;
        p->tris[CLR] = p->mask;
    }
    for (uint8_t n = 1; n <= IO_GPIOS; n++)
        io_gpio_config(n, GPIO_IN, PULL_DOWN, false);
    vmid_init();
    adc_init();
    i2c_init();
    delay_ms(2);
    io_detect();
    for (uint8_t i = 0; i < IO_AOS; i++)
        ao_out(i, 0);                   /* a core reset leaves the outputs at 0 V */
}
