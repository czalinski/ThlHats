#include <xc.h>
#include <sys/kmem.h>
#include <stddef.h>
#include <string.h>
#include "board.h"
#include "settings.h"

#define MAGIC       0x54484C53u     /* "SLHT" */
#define VERSION     2u
#define PAGE_KVA    0x9D0FF000u     /* last page of the 1 MB program flash */
#define PAGE_SIZE   4096u
#define PAGE_KVA1   (0xA0000000u | (PAGE_KVA & 0x1FFFFFFFu))   /* uncached: no stale cache lines after a write */

/* keep the linker out of the settings page; noload: not in the hex file */
static const uint8_t settings_page[PAGE_SIZE]
    __attribute__((space(prog), address(PAGE_KVA), aligned(PAGE_SIZE), noload, used));

settings_t settings;
static bool loaded_from_flash;

static const settings_t defaults = {
    .magic = MAGIC,
    .version = VERSION,
    .ip = { 192, 168, 1, 50 },
    .mask = { 255, 255, 255, 0 },
    .gw = { 192, 168, 1, 1 },
    .ser = {
        { 9600, 8, 'N', 1, 0 }, { 9600, 8, 'N', 1, 0 },
        { 9600, 8, 'N', 1, 0 }, { 9600, 8, 'N', 1, 0 },
    },
};

static uint32_t crc32(const void *p, uint32_t n)
{
    const uint8_t *b = p;
    uint32_t c = 0xFFFFFFFFu;
    while (n--) {
        c ^= *b++;
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & -(c & 1u));
    }
    return ~c;
}

void settings_load(void)
{
    const settings_t *s = (const settings_t *)PAGE_KVA1;
    (void)settings_page;
    if (s->magic == MAGIC && s->version == VERSION
        && s->crc == crc32(s, offsetof(settings_t, crc))) {
        settings = *s;
        loaded_from_flash = true;
    } else {
        settings = defaults;
    }
}

bool settings_from_flash(void)
{
    return loaded_from_flash;
}

/* one NVM operation (DS60001519D 5.0): NVMOP written with WREN = 0, then the
 * unlock sequence and WR with interrupts off */
static bool nvm_op(uint32_t op, uint32_t pa)
{
    NVMADDR = pa;
    NVMCON = op;
    NVMCONSET = _NVMCON_WREN_MASK;
    delay_us(10);
    uint32_t ie = __builtin_disable_interrupts();
    NVMKEY = 0;
    NVMKEY = 0xAA996655u;
    NVMKEY = 0x556699AAu;
    NVMCONSET = _NVMCON_WR_MASK;
    while (NVMCON & _NVMCON_WR_MASK) { }
    if (ie & 1u)
        __builtin_enable_interrupts();
    NVMCONCLR = _NVMCON_WREN_MASK;
    return !(NVMCON & (_NVMCON_WRERR_MASK | _NVMCON_LVDERR_MASK));
}

bool settings_save(void)
{
    uint32_t words[(sizeof(settings_t) + 15u) / 16u * 4u];
    settings.magic = MAGIC;
    settings.version = VERSION;
    settings.crc = crc32(&settings, offsetof(settings_t, crc));
    memset(words, 0xFF, sizeof words);
    memcpy(words, &settings, sizeof settings);

    uint32_t pa = KVA_TO_PA(PAGE_KVA);
    if (!nvm_op(4u, pa))                            /* page erase */
        return false;
    for (uint32_t k = 0; k < sizeof words / 4u; k += 4u) {
        NVMDATA0 = words[k];
        NVMDATA1 = words[k + 1u];
        NVMDATA2 = words[k + 2u];
        NVMDATA3 = words[k + 3u];
        if (!nvm_op(2u, pa + k * 4u))               /* quad word program */
            return false;
    }
    return memcmp((const void *)PAGE_KVA1, &settings, sizeof settings) == 0;
}
