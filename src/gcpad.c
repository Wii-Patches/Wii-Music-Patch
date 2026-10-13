/* GameCube controller / Classic Controller support for Wii Music.
 *
 * The game's Remocon objects call KPADRead once per channel per frame and the
 * startup screens call it from two more places; every WPAD connection check goes
 * through WPADProbe.  Both call sites are redirected to the two wrappers below
 * (hook_kpad, hook_probe).  A GameCube pad in port N drives Wii Remote N; a
 * Classic Controller plugged into a Wii Remote drives that Wii Remote.  Either way
 * the channel is presented to the game as a Wii Remote with a Nunchuk:
 *
 *   A, B, X, Y      Wii Remote A, B, 1, 2
 *   L / ZL          shake the Nunchuk hand (the left hand)
 *   R / ZR          shake the Wii Remote hand (the right hand)
 *   Z, Start (GC)   HOME Menu       Home (Classic)   HOME Menu
 *   + / - (Classic) + and -         GC control stick left / right   - / + (switch instruments)
 *   D-pad           D-pad
 *   control stick   Nunchuk stick   C stick / right stick   IR pointer
 *
 * The game never links PAD, so nothing polls the pads: gc_poll() drives the Serial
 * Interface's auto-polling the way Barrel Blast Patch does (hardware-tested there).
 * Addresses of the game's own functions and SI variables come in as -D macros.
 */
typedef unsigned int u32;
typedef signed int s32;
typedef unsigned short u16;
typedef unsigned char u8;
typedef signed char s8;

#define R32(a) (*(volatile u32 *)(a))
#define SI_OUT(c) (0xCD006400u + 0xC * (c))
#define SI_INH(c) (0xCD006404u + 0xC * (c))
#define SI_INL(c) (0xCD006408u + 0xC * (c))
#define SI_POLL   (0xCD006430u)
#define SI_COMCSR (0xCD006434u)
#define SI_SR     (0xCD006438u)

/* Wii Remote button bits */
#define WM_LEFT  0x0001
#define WM_RIGHT 0x0002
#define WM_DOWN  0x0004
#define WM_UP    0x0008
#define WM_PLUS  0x0010
#define WM_TWO   0x0100
#define WM_ONE   0x0200
#define WM_B     0x0400
#define WM_A     0x0800
#define WM_MINUS 0x1000
#define WM_HOME  0x8000

struct ch {
    u32 magic;   /* 0x00 */
    u32 prev_hold;
    s32 ptr_x, ptr_y;       /* IR pointer, thousandths of the screen */
    u32 swing[2];           /* frames into the swing of each hand (0 = idle): [0] left/Nunchuk, [1] right/remote */
    u32 prev_sh[2];         /* shoulder buttons last frame */
    u32 src;                /* 0 nobody, 1 GameCube pad, 2 Classic Controller */
    u32 frames;
    float last[2][3];       /* last acceleration written for each hand */
    u32 norep;
    u32 last_h, last_l;
    float last_mag[2];
};
struct gl {
    u32 probe_tb, poll_tb, busy_tb, rr;
};
#define CH(c) ((volatile struct ch *)(STATE + 0x60 * (c)))
#define GL ((volatile struct gl *)(STATE + 0x180))
#define MAGIC 0x574D5031u   /* 'WMP1' */

static inline u32 tb(void)
{
    u32 t;
    __asm__ volatile("mftb %0" : "=r"(t));
    return t;
}

static u32 (*const KPADRead)(u32, void *, u32) = (void *)FN_KPADREAD;
static s32 (*const WPADProbe)(u32, u32 *) = (void *)FN_WPADPROBE;

/* ---- the pad ----------------------------------------------------------- */

static inline int gc_in(u32 c, u32 *h, u32 *l)
{
    u32 v = R32(SI_INH(c));
    if ((v & 0x80000000u) || !(v & 0x00800000u))
        return 0;
    *h = v;
    *l = R32(SI_INL(c));
    return 1;
}

static void gc_poll(void)
{
    volatile u32 *types = (volatile u32 *)SI_TYPES;
    u32 now = tb(), sisr, poll, mask = 0, c;
    s32 busy;

    if (now - GL->poll_tb < 300000u)        /* once per frame is plenty; four wrappers run per frame */
        return;
    GL->poll_tb = now;

    /* probe one unconfirmed port at a time, at most every 0.25 s: probing every
     * frame collided with the pads' own polling on hardware */
    if (now - GL->probe_tb >= 15187500u) {
        GL->probe_tb = now;
        for (c = 0; c < 4; c++) {
            u32 k = (GL->rr + c) & 3, t = types[k];
            if (!(!(t & 0x80) && (t & 0x18000000u) == 0x08000000u)) {
                GL->rr = k + 1;
                ((u32 (*)(u32))FN_SIGETTYPE)(k);
                break;
            }
        }
    }

    /* an unplugged pad latches NOREP; si:: never reads it, so copy a persistent one
     * into the type cache, which makes SIGetType probe the port again later */
    sisr = R32(SI_SR);
    for (c = 0; c < 4; c++) {
        if (sisr & (0x08000000u >> (8 * c))) {
            if (CH(c)->norep < 10)
                CH(c)->norep++;
            else
                types[c] = 8;
        } else {
            CH(c)->norep = 0;
        }
        R32(SI_OUT(c)) = 0x00400300u;       /* poll command */
    }
    R32(SI_SR) = (sisr & 0x0F0F0F0Fu) | 0x80000000u;   /* ack errors, latch OUT */

    for (c = 0; c < 4; c++) {
        u32 t = types[c];
        if (!(t & 0x80) && (t & 0x18000000u) == 0x08000000u)
            mask |= 0x88u >> c;             /* ENn + VBCPYn */
    }
    poll = R32(SI_POLL) & ~0xFFu;
    if (!(poll & 0xFF00u))
        poll |= 0x0100u;
    R32(SI_POLL) = poll | mask;
    /* si:: rewrites SIPOLL from its own shadow on every retrace */
    R32(SI_SHADOW) = (R32(SI_SHADOW) & ~0xFFu) | mask;

    /* a pad unplugged mid-transfer leaves si::'s busy flag wedged; force it idle after a second */
    busy = (s32)R32(SI_BUSY);
    if (busy == -1) {
        GL->busy_tb = 0;
    } else if (GL->busy_tb == 0) {
        GL->busy_tb = now | 1;
    } else if (now - GL->busy_tb >= 60750000u) {
        u32 lvl = ((u32 (*)(void))FN_OSDISABLE)();
        R32(SI_BUSY) = (u32)-1;
        R32(SI_COMCSR) = 0x80000000u;
        ((void (*)(u32))FN_OSRESTORE)(lvl);
        GL->busy_tb = 0;
    }
}

/* ---- KPADStatus (old SDK, 0x84 bytes) ----------------------------------- */

#define KS_SIZE 0x84
struct kstat {
    u32 hold, trig, release;        /* 00 */
    float acc[3];                   /* 0C  Wii Remote */
    float acc_value, acc_speed;     /* 18 */
    float pos[2];                   /* 20  IR pointer */
    u8 pad1[0x5C - 0x28];
    u8 dev_type, dev_error, dpd_valid, data_format;   /* 5C */
    float stick[2];                 /* 60  Nunchuk stick */
    float nacc[3];                  /* 68  Nunchuk acceleration */
    float nacc_value, nacc_speed;   /* 74 */
};

static float fabs_(float x) { return x < 0 ? -x : x; }
static float clampf(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }

/* one hand's acceleration for frame k of a swing: rest + a spike down, then the stop */
#define SWING_FRAMES 8
static const float swing_amp[SWING_FRAMES] = { -2.5f, -3.5f, -2.0f, 1.5f, 4.0f, 3.0f, 1.0f, 0.0f };

static void hand_acc(float *out, u32 k)    /* k = 0: at rest */
{
    float a = k ? swing_amp[k - 1] : 0.0f;
    out[0] = 0.0f;
    out[1] = a * 0.35f;
    out[2] = 1.0f + a;
}

/* GameCube pad word -> Wii Remote buttons (A,B,X,Y,Start,Z,D-pad) */
static u32 gc_buttons(u32 h)
{
    u32 b = 0;
    if (h & 0x01000000u) b |= WM_A;
    if (h & 0x02000000u) b |= WM_B;
    if (h & 0x04000000u) b |= WM_ONE;       /* X */
    if (h & 0x08000000u) b |= WM_TWO;       /* Y */
    if (h & 0x10000000u) b |= WM_HOME;      /* Start */
    if (h & 0x00100000u) b |= WM_HOME;      /* Z */
    if (h & 0x00080000u) b |= WM_UP;
    if (h & 0x00040000u) b |= WM_DOWN;
    if (h & 0x00020000u) b |= WM_RIGHT;
    if (h & 0x00010000u) b |= WM_LEFT;
    return b;
}

/* Classic Controller hold word -> Wii Remote buttons */
static u32 cc_buttons(u32 c)
{
    u32 b = 0;
    if (c & 0x0010) b |= WM_A;
    if (c & 0x0040) b |= WM_B;
    if (c & 0x0008) b |= WM_ONE;            /* X */
    if (c & 0x0020) b |= WM_TWO;            /* Y */
    if (c & 0x0400) b |= WM_PLUS;
    if (c & 0x1000) b |= WM_MINUS;
    if (c & 0x0800) b |= WM_HOME;
    if (c & 0x0001) b |= WM_UP;
    if (c & 0x4000) b |= WM_DOWN;
    if (c & 0x8000) b |= WM_RIGHT;
    if (c & 0x0002) b |= WM_LEFT;
    return b;
}

/* control stick left / right -> - / + (instrument switching) */
static u32 gc_stick_buttons(u32 h)
{
    s32 x = (s32)((h >> 8) & 0xFF) - 128;
    if (x <= -48) return WM_MINUS;
    if (x >= 48) return WM_PLUS;
    return 0;
}

static float sqrt_(float x)
{
    float r, i;
    if (x <= 0.0f) return 0.0f;
    r = x > 1.0f ? x * 0.5f : 1.0f;
    for (i = 0; i < 8; i++) r = 0.5f * (r + x / r);
    return r;
}

static s32 stick_pct(u32 byte)              /* GameCube stick byte -> -100..100 */
{
    return (s32)(byte & 0xFF) - 128;
}

static void move_pointer(volatile struct ch *s, s32 rx, s32 ry)
{
    s32 dz = POINTER_DEADZONE;
    if (rx > dz || rx < -dz) s->ptr_x = (s32)(clampf((float)s->ptr_x + (float)rx * POINTER_SPEED, -1000.0f, 1000.0f));
    if (ry > dz || ry < -dz) s->ptr_y = (s32)(clampf((float)s->ptr_y - (float)ry * POINTER_SPEED, -1000.0f, 1000.0f));
}

/* Rewrite `n` samples of buf as a Wii Remote + Nunchuk driven by the pad / Classic Controller. */
static void drive(u32 chan, struct kstat *buf, u32 n, u32 src, u32 hold, s32 lx, s32 ly, s32 rx, s32 ry,
                  u32 swl, u32 swr, u32 real_hold)
{
    volatile struct ch *s = CH(chan);
    u32 sh[2] = { swl, swr }, i, h, trig, rel;
    float cur[2][3], rest[2][3];
    float px, py, mag;

    for (h = 0; h < 2; h++) {
        if (sh[h] && !s->prev_sh[h])
            s->swing[h] = 1;
        s->prev_sh[h] = sh[h];
        hand_acc(cur[h], s->swing[h]);
        for (i = 0; i < 3; i++) rest[h][i] = s->last[h][i];
        if (s->swing[h]) {
            s->swing[h]++;
            if (s->swing[h] > SWING_FRAMES + 1)
                s->swing[h] = 0;
        }
        for (i = 0; i < 3; i++) s->last[h][i] = cur[h][i];
    }

    move_pointer(s, rx, ry);
    px = (float)s->ptr_x * 0.001f;
    py = (float)s->ptr_y * 0.001f;

    hold |= real_hold;
    trig = hold & ~s->prev_hold;
    rel = s->prev_hold & ~hold;
    s->prev_hold = hold;

    for (i = 0; i < n; i++) {
        struct kstat *k = &buf[i];
        /* sample 0 is the newest; older ones step back from the previous frame's value toward it */
        float t = (float)(n - i) / (float)n;
        u32 j;
        u8 *z = (u8 *)k;
        for (j = 0; j < KS_SIZE; j++) z[j] = 0;
        k->hold = hold;
        k->trig = i == 0 ? trig : 0;
        k->release = i == 0 ? rel : 0;
        for (j = 0; j < 3; j++) {
            k->acc[j] = rest[1][j] + (cur[1][j] - rest[1][j]) * t;
            k->nacc[j] = rest[0][j] + (cur[0][j] - rest[0][j]) * t;
        }
        /* KPAD reports the magnitude and how fast it is changing (the game's gesture code reads both) */
        mag = sqrt_(k->acc[0] * k->acc[0] + k->acc[1] * k->acc[1] + k->acc[2] * k->acc[2]);
        k->acc_value = mag;
        k->acc_speed = fabs_(mag - s->last_mag[1]) * 0.5f;
        if (i == 0) s->last_mag[1] = mag;
        mag = sqrt_(k->nacc[0] * k->nacc[0] + k->nacc[1] * k->nacc[1] + k->nacc[2] * k->nacc[2]);
        k->nacc_value = mag;
        k->nacc_speed = fabs_(mag - s->last_mag[0]) * 0.5f;
        if (i == 0) s->last_mag[0] = mag;
        k->pos[0] = px;
        k->pos[1] = py;
        k->dev_type = 1;                    /* Nunchuk */
        k->dev_error = 0;
        k->dpd_valid = 2;
        k->stick[0] = clampf((float)lx * 0.01f, -1.0f, 1.0f);
        k->stick[1] = clampf((float)ly * 0.01f, -1.0f, 1.0f);
    }
    s->src = src;
    s->frames++;
}

/* the wrapper for every `bl KPADRead` */
s32 hook_kpad(u32 chan, void *buf, u32 n)
{
    s32 r = KPADRead(chan, buf, n);
    volatile struct ch *s;
    struct kstat *k = (struct kstat *)buf;
    u32 h, l, cnt = n < 3 ? n : 3;

    if (chan > 3)
        return r;
    gc_poll();
    s = CH(chan);
    if (s->magic != MAGIC) {
        u32 *p = (u32 *)s, i;
        for (i = 0; i < 0x18; i++) p[i] = 0;
        s->last[0][2] = s->last[1][2] = s->last_mag[0] = s->last_mag[1] = 1.0f;       /* both hands start at rest */
        s->magic = MAGIC;
    }
    if (!cnt)
        return r;

    if ((R32(CFG) & 1) && gc_in(chan, &h, &l)) {
        s->last_h = h;
        s->last_l = l;
        drive(chan, k, cnt, 1, gc_buttons(h) | gc_stick_buttons(h), stick_pct(h >> 8), stick_pct(h), stick_pct(l >> 24), stick_pct(l >> 16),
              (h & 0x00400000u) != 0, (h & 0x00200000u) != 0, 0);
        return cnt;
    }
    if ((R32(CFG) & 2) && r > 0 && k->dev_type == 2) {
        /* Classic Controller in a Wii Remote: hold at +0x60, sticks as floats (about -1..1) */
        u32 c = *(u32 *)((u8 *)k + 0x60);
        float *f = (float *)((u8 *)k + 0x6C);
        u32 real = k->hold;
        drive(chan, k, cnt, 2, cc_buttons(c), (s32)(f[0] * 100.0f), (s32)(f[1] * 100.0f), (s32)(f[2] * 100.0f),
              (s32)(f[3] * 100.0f), (c & 0x2080) != 0, (c & 0x0204) != 0, real);
        return cnt;
    }
    s->src = 0;
    s->swing[0] = s->swing[1] = 0;
#ifdef LOGACC
    /* debug build: record the real controller's acceleration (acc, acc_value, acc_speed; same for the Nunchuk),
     * 10 floats per frame, in a ring of 24 at STATE+0x200 */
    if (chan == 0 && r > 0) {
        volatile u32 *idx = (volatile u32 *)(STATE + 0x1FC);
        volatile float *ring = (volatile float *)(STATE + 0x200);
        u32 i = *idx % 24, j;
        for (j = 0; j < 3; j++) { ring[i * 10 + j] = k->acc[j]; ring[i * 10 + 5 + j] = k->nacc[j]; }
        ring[i * 10 + 3] = k->acc_value; ring[i * 10 + 4] = k->acc_speed;
        ring[i * 10 + 8] = k->nacc_value; ring[i * 10 + 9] = k->nacc_speed;
        *idx = *idx + 1;
    }
#endif
    return r;
}

/* the wrapper for every `bl WPADProbe`: a pad (or a Classic Controller) makes the channel look like a Wii Remote with a Nunchuk */
s32 hook_probe(u32 chan, u32 *type)
{
    s32 r = WPADProbe(chan, type);
    u32 h, l;

    if (chan > 3)
        return r;
    gc_poll();
    if ((R32(CFG) & 1) && gc_in(chan, &h, &l)) {
        if (type)
            *type = 1;
        return 0;
    }
    if ((R32(CFG) & 2) && r == 0 && type && *type == 2)
        *type = 1;
    return r;
}
