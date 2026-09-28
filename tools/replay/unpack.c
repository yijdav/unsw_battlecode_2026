#include <stdint.h>
#include <stddef.h>
#include <string.h>
long long capnp_unpack(const uint8_t* in, size_t n, uint8_t* out, size_t cap) {
    size_t i = 0, o = 0;
    while (i < n) {
        uint8_t tag = in[i++];
        if (o + 8 > cap) return -1;
        for (int b = 0; b < 8; ++b) {
            if (tag & (1u << b)) { if (i >= n) return -2; out[o + b] = in[i++]; }
            else out[o + b] = 0;
        }
        o += 8;
        if (tag == 0x00) {
            if (i >= n) return -3;
            size_t z = in[i++];
            if (o + z * 8 > cap) return -1;
            memset(out + o, 0, z * 8); o += z * 8;
        } else if (tag == 0xff) {
            if (i >= n) return -4;
            size_t r = in[i++];
            if (o + r * 8 > cap) return -1;
            if (i + r * 8 > n) return -5;
            memcpy(out + o, in + i, r * 8); o += r * 8; i += r * 8;
        }
    }
    return (long long)o;
}
