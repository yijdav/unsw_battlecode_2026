import ctypes, struct, array, os, sys
_lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libunpack.dylib'))
_lib.capnp_unpack.restype = ctypes.c_longlong
_lib.capnp_unpack.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
def unpack(data):
    cap = max(len(data) * 10, 1 << 20)
    while True:
        out = ctypes.create_string_buffer(cap)
        n = _lib.capnp_unpack(data, len(data), out, cap)
        if n == -1:
            cap *= 2; continue
        if n < 0:
            raise ValueError(f'unpack error {n}')
        return out.raw[:n]
class Msg:
    def __init__(self, raw):
        nseg = struct.unpack_from('<I', raw, 0)[0] + 1
        sizes = struct.unpack_from(f'<{nseg}I', raw, 4)
        off = 4 + 4 * nseg
        off += (-off) % 8
        self.segs = []
        for s in sizes:
            self.segs.append(raw[off:off + s * 8])
            if len(self.segs[-1]) != s * 8:
                raise ValueError('truncated segment')
            off += s * 8
    def word(self, seg, idx):
        return struct.unpack_from('<Q', self.segs[seg], idx * 8)[0]
    def ptr(self, seg, idx):
        w = self.word(seg, idx)
        t = w & 3
        if t == 2:
            land = (w >> 2) & 1
            off = (w >> 3) & ((1 << 29) - 1)
            sid = w >> 32
            if not land:
                return self.ptr(sid, off)
            w2 = self.word(sid, off)
            tag = self.word(sid, off + 1)
            return self._decode(tag, w2 >> 32, (w2 >> 3) & ((1 << 29) - 1), True)
        return self._decode(w, seg, idx, False)
    def _decode(self, w, seg, idx, direct):
        t = w & 3
        if w == 0:
            return None
        o = (w >> 2) & 0x3fffffff
        if o & 0x20000000:
            o -= 0x40000000
        start = idx if direct else idx + 1 + o
        if t == 0:
            return ('struct', seg, start, (w >> 32) & 0xffff, w >> 48)
        if t == 1:
            return ('list', seg, start, (w >> 32) & 7, w >> 35)
        raise ValueError(f'ptr type {t}')
    def root(self):
        return self.ptr(0, 0)
    def struct_ptr(self, s, i):
        _, seg, start, dw, pw = s
        if i >= pw:
            return None
        return self.ptr(seg, start + dw + i)
    def u16(self, s, byteoff):
        _, seg, start, dw, pw = s
        if byteoff + 2 > dw * 8: return 0
        return struct.unpack_from('<H', self.segs[seg], start * 8 + byteoff)[0]
    def u32(self, s, byteoff):
        _, seg, start, dw, pw = s
        if byteoff + 4 > dw * 8: return 0
        return struct.unpack_from('<I', self.segs[seg], start * 8 + byteoff)[0]
    def i32(self, s, byteoff):
        _, seg, start, dw, pw = s
        if byteoff + 4 > dw * 8: return 0
        return struct.unpack_from('<i', self.segs[seg], start * 8 + byteoff)[0]
    def u64(self, s, byteoff):
        _, seg, start, dw, pw = s
        if byteoff + 8 > dw * 8: return 0
        return struct.unpack_from('<Q', self.segs[seg], start * 8 + byteoff)[0]
    def text(self, p):
        if p is None: return None
        _, seg, start, es, cnt = p
        b = self.segs[seg][start * 8:start * 8 + cnt]
        return b.rstrip(b'\0').decode('utf-8', 'replace')
    def composite(self, p):
        _, seg, start, es, cnt = p
        assert es == 7
        tag = self.word(seg, start)
        n = (tag >> 2) & 0x3fffffff
        dw = (tag >> 32) & 0xffff
        pw = tag >> 48
        return seg, start + 1, n, dw, pw
END_REASON = {0: 'elimination', 1: 'round_limit'}
def read_result(data):
    msg = Msg(unpack(data))
    r = msg.root()
    fmt = msg.u32(r, 0)
    seed_which = msg.u16(r, 4)
    seed = msg.u64(r, 8) if seed_which == 1 else None
    botA = msg.text(msg.struct_ptr(r, 1))
    botB = msg.text(msg.struct_ptr(r, 2))
    mp = msg.text(msg.struct_ptr(r, 0)) or ''
    mapname = None
    for line in mp.splitlines()[:5]:
        if line.startswith('MAP_NAME'):
            mapname = line.split(None, 1)[1] if len(line.split()) > 1 else ''
    res = msg.struct_ptr(r, 4)
    out = dict(fmt=fmt, seed=seed, botA=botA, botB=botB, mapname=mapname)
    if res is None:
        out['winner'] = 'unfinished'
        return out
    terminated = msg.u16(res, 0) & 1
    endr = msg.u16(res, 2)
    which = msg.u16(res, 4)
    win = msg.u16(res, 6)
    out['terminated'] = terminated
    out['end'] = END_REASON.get(endr, endr)
    out['winner'] = ('A', 'B')[win] if which == 1 else 'draw'
    for k, i in (('A', 0), ('B', 1)):
        t = msg.struct_ptr(res, i)
        out['team' + k] = (msg.i32(t, 0), msg.i32(t, 4), msg.i32(t, 8)) if t else None
    ev = msg.struct_ptr(r, 3)
    rounds = None
    if ev is not None:
        seg, st, n, dw, pw = msg.composite(ev)
        stride = (dw + pw) * 8
        buf = msg.segs[seg][st * 8: st * 8 + n * stride]
        a = array.array('H'); a.frombytes(buf[:len(buf) - len(buf) % 2])
        k = stride // 2
        rounds = a[::k].count(0)
        out['events'] = n
    out['rounds'] = rounds
    return out
if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(f, read_result(open(f, 'rb').read()))
