#include "helper.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <unordered_map>
#include <vector>

using unswbc::Direction;

namespace {

constexpr int R = unswbc::Constants::VISION_RADIUS;
constexpr int VS = unswbc::Constants::VISION_SIZE;
constexpr int STALE = 20;
constexpr int PEARL_MEMORY = 40;
constexpr int INF = 1 << 20;

struct Knobs {
    int feed_start_small = 420;
    int feed_start_big = 294;
    int split_at = 4;
    int feed_last_round = 496;
    int pf_feed_start = 200;
    int pf_maps = 2;
    int sl_feed_start = 300;
    int tr_feed_start = 350;
    int sc_feed_start = 0;
    int au_feed_start = 0;
    int crowded_pearls = 6;
    bool escape_split = true;
    double explore_value = 0.1177;
    double fountain_value = 0.4022;
    bool cycle_test = false;
    double exit_penalty = 7.256;
    int split_crowd = 99;
    bool remote_hunt = false;
    int sighting_len = 8;
    int hunt_start = 150;
    int hunt_radius = 20;
    bool boxed_suicide = true;
    bool split_report = true;
    bool sight_refresh = true;
    bool sight_partial = true;
    bool feed_guard = true;
    int feed_margin = 0;
    int feed_min_age = 1;
    double feed_self_frac = 0;
    bool trap_model = true;
    bool trap_model_feed = true;
    int model_slack = 0;
    bool horizon_cap = true;
    int split_guard_len = 6;
    bool split_guard_champ = true;
    bool uturn_guard = true;
    int split_guard_mode = 0;
    bool split_guard_feed = true;
    int split_shout = 3;
    bool split_need_tail = true;
    bool tombstone = true;
    double portal_explore = 47.07;
    double portal_entry = 0.3082;
    bool portal_feed = true;
    int portal_max_len = 99;
    int portal_region = 300;
    bool portal_share = true;
    int portal_gossip = 2;
    bool portal_need_tail = true;
    double blind_land = 31.25;
    double champ_blind_land = 300;
    double champ_portal_cell = 100;
    int spawn_lead = 1;
    double spawn_block = 45.43;
    int reach_cap = 5;
    bool reach_clip = true;
    double reach_champ = 5000;
    double reach_champ_edge = 104.3;
    double reach_champ_far = 83.59;
    int reach_long_len = 5;
    double reach_long = 21.21;
    double reach_long_edge = 30;
    double reach_adj = 311.7;
    double reach_adj_len = 20;
    int reach_adj_units = 999;
    int reach_pearl_len = 8;
    double reach_corner = 2000;
    double reach_corner_long = 30;
    bool sprint_ram = true;
    int sprint_margin = 1;
    int sprint_max_len = 3;
    int sprint_steps = 3;
    int guard_radius = 5;
    bool guard_chase = false;
    int sprint_min_units = 1;
    bool pocket_delay = true;
    bool delay_in_feed = true;
    bool pocket_harvest = true;
    int harvest_pearls = 2;
    double harvest_cost = 15.18;
    int harvest_enemy_dist = 0;
    bool harvest_depth_check = true;
    bool harvest_tube = true;
    bool harvest_clear = true;
    bool ram_gate = true;
    int ram_min_units = 3;
    int ram_long_units = 2;
    int eq_min_units = 8;
    int eq_free_gap = 15;
    int eq_local = 1;
    int eq_window = 0;
    double eq_avoid = 10.2;
    bool eq_feed = true;
    bool ram_trap = true;
    bool no_reverse = true;
    bool history_dedupe = true;
    bool chain_plain = true;
    bool history_young = true;
    bool history_seed = true;
    double young_blind_land = 150;
    bool danger_step = true;
    bool tombstone_body = true;
    bool reach_clip_portal = true;
    int hold_danger = 1;
    bool hold_danger_tail = true;
    bool guard_fresh = true;
    bool ram_escape_full = true;
    int horizon_slack = 0;
    double blind_route = 0.3;
    double exit_calm = 0;
    int feed_reach = 7;
    int feed_min_units = 0;
    int shield_len = 8;
    int shield_tail = 2;
    bool shield_all = true;
    int shield_last = 500;
    bool blind_tie = false;
    bool blind_feed_exempt = false;
    int calm_radius = 0;
    bool calm_zero = false;
    int crowd_reach = 0;
    int portal_starve = 2;
    int portal_big_n = 2048;
    int split_reserve = 0;
    bool shield_champ = false;
    int split_tail_exits = 2;
    int map_prior = 130;
    double pr_explore = 60;
    double pr_blind_land = 10;
    double pr_blind_route = 1;
    double pr_land_friend = 300;
    int open_maps = 512;
    int open_rounds = 30;
    double open_portal = 0;
    double open_blind = -1;
    double open_entry = 0.6;
    int open_min_len = 2;
    bool open_closed_only = false;
    int open_max_ids = 1;
    int open_from = 6;
    int eq_until = 0;
    int eq_min_early = 4;
    int eq_local_early = 1;
    int eq_maps = 0;
    int ste_until = 1000;
    int ste_maps = 1024;
    int detect_maps = 15360;
    int sm_until = 0;
    int sm_early = 0;
    int sm_maps = 0;
    int pr_fount_mask = -1;
    int ctr_until = 30;
    double ctr_bonus = 15;
    int ctr_maps = 2048;
    int cup_until = 0;
    double cup_bonus = 0;
    int cup_maps = 0;
    int use_symmetry = 0;
    int sym_conf = 0;
    double portal_reserve = 0;
    int portal_turns = 0;
    int mapbook = 5120;
    int book_rounds = 60;
    int book_region_cap = 3;
    double book_w = 10;
    int book_min_len = 3;
    int lookahead = 0;
    int lookahead_depth = 2;
    int lookahead_budget = 20000;
    bool champ_lock = false;
    int champ_lock_round = 200;
    double champ_pearl_mult = 2;
    bool tube_farm = false;
    int tail_strike = 0;
    bool ts_moved = true;
    int pearl_sprint = 0;
    int ps_contest = 3;
    int keep_long_len = 0;
    int keep_until = 300;
    int keep_maps = 16384;
    bool map_knobs_on = true;
    int sprint_rule = 0;
    int sprint_reach_cap = 0;
    int q_split_until = 1000;
    int q_keep = 0;
    double q_safe = 0;
    double q_adj = 100000;
    bool q_no_ram = false;
    int q_area = 0;
    double q_area_w = 100;
    int q_flee = 0;
    double q_room = 0;
    int q_champ = 0;
    int q_alive_age = 8;
    int q_champ_gap = 0;
    int q_feed_start = 0;
    bool q_feed_long = false;
    int q_hunt_len = 0;
    double q_hunt_w = 0;
    bool q_hunt_report = false;
    int q_hunt_age = 16;
    double q_land = 0;
    int q_hunt_units = 2;
    int q_min_units = 0;
    bool q_log = false;
    int q_esc_keep = 0;
    int q_release = 0;
    bool q_no_pocket = false;
    int q_hide = 0;
    double q_hide_w = 0;
    double q_tube = 0;
    double q_mate_adj = 0;
    int q_terr = 0;
    double q_terr_w = 0;
    double q_box = 0;
    int q_feed_near = 0;
    int q_on_units = 0;
    bool q_terr_mates = false;
    int q_room_r = 2;
    double q_away = 0;
    double q_exit = 0;
    int q_min_n = 0;
    double q_blind = 0;
    int q_slack = 0;
    int q_min_start = 0;
    int is_feed_start = 0;
    int sf_dist = 0;
    double sf_grow = 0;
    int sf_maps = 0;
    int ce_steps = 0;
    int ce_min_len = 5;
    int ce_maps = 0;
    bool board_on = false;
    int au64_feed_start = 0;
    int un64_feed_start = 0;
    int mz_feed_start = 350;
    bool board_log = false;
    int board_ev = 2;
    bool fx_relay = false;
    int fx_stale = 0;
    bool fx_tomb = false;
    int fx_maps = 0;
    int q_nofeed = 0;
    bool sf_split = false;
    int kb_len = 0;
    int kb_from = 0;
    int kb_maps = 0;
    bool kb_best = false;
} K;

int W, H, N;
int round_num;
int my_id;
unswbc::Team my_team = unswbc::Team::A;
int my_queen = -1, foe_queen = -1;
bool queen_known = false;
inline int free_steps(int len) { return K.sprint_rule ? (len + 3) / 4 : 1; }
inline int max_steps(int len) { return K.sprint_rule ? (len + 3) / 4 + len - 2 : len - 1; }
inline int true_steps(int len) { return std::max(1, (len + 3) / 4 + len - 2); }
int dir_index(Direction d) {
    switch (d.value) {
    case Direction::NORTH: return 0;
    case Direction::EAST: return 1;
    case Direction::SOUTH: return 2;
    default: return 3;
    }
}
Direction const DIRS[4] = {Direction::NORTH, Direction::EAST, Direction::SOUTH, Direction::WEST};
int const DX[4] = {0, 1, 0, -1};
int const DY[4] = {-1, 0, 1, 0};

inline int cell_of(int x, int y) { return ((y % H + H) % H) * W + ((x % W + W) % W); }
inline int cx(int c) { return c % W; }
inline int cy(int c) { return c / W; }
inline int adj(int c, int d) { return cell_of(cx(c) + DX[d], cy(c) + DY[d]); }
inline int wrapd(int a, int b, int m) { int d = std::abs(a - b); return std::min(d, m - d); }
inline int manhattan(int a, int b) { return wrapd(cx(a), cx(b), W) + wrapd(cy(a), cy(b), H); }
inline int chebyshev(int a, int b) { return std::max(wrapd(cx(a), cx(b), W), wrapd(cy(a), cy(b), H)); }

std::vector<uint8_t> edge_n, edge_w;
std::vector<int> portal_n, portal_w;
std::vector<int> partner_n, partner_w;
std::vector<int> pearl_seen;
std::vector<int> spawn_at;
std::vector<int> seen_round;
std::vector<uint8_t> quick_seen;
std::vector<int> quick_round;
struct PortalEnd { int cell; bool north; };
std::unordered_map<int, std::vector<PortalEnd>> portals;
struct PairRec { int a, b; bool north; int last; };
std::vector<PairRec> pairs;

std::vector<int> occ_stamp, occ_id, self_seg, ff_stamp, ff_free, rim_stamp, ptl_stamp;
std::vector<uint8_t> occ_head, occ_enemy, occ_dir;
std::vector<int> threat_at, threat_lt, threat_le, reach_mark, reach_dist, rsv_mark, tube_mark, qd, qd_at, qt, qt_at;
int stamp = 0, reach_id = 0, rsv_id = 0, tube_id = 0;
inline bool occupied(int c) { return occ_stamp[c] == stamp; }

void link_pair(int a, int b, bool north) {
    auto& pa = north ? partner_n : partner_w;
    if (pa[a] == b && pa[b] == a) return;
    pa[a] = b; pa[b] = a;
    (north ? edge_n : edge_w)[a] = 2; (north ? edge_n : edge_w)[b] = 2;
    for (auto& p : pairs)
        if (p.north == north && (p.a == a || p.b == a || p.a == b || p.b == b)) { p.a = a; p.b = b; p.last = round_num; return; }
    pairs.push_back({a, b, north, round_num});
}

void remember_portal(int id, int cell, bool north) {
    auto& ends = portals[id];
    for (auto const& e : ends) if (e.cell == cell && e.north == north) return;
    ends.push_back({cell, north});
    if (ends.size() == 2 && ends[0].north == ends[1].north) link_pair(ends[0].cell, ends[1].cell, north);
}

int edge_key(int c, int d, bool& north) {
    north = d == 0 || d == 2;
    return d == 2 ? adj(c, 2) : d == 1 ? adj(c, 1) : c;
}

int step(int c, int d, bool* via_portal = nullptr) {
    bool north;
    int const key = edge_key(c, d, north);
    uint8_t const kind = north ? edge_n[key] : edge_w[key];
    if (via_portal) *via_portal = false;
    if (kind == 1) return -1;
    if (kind == 0) return adj(c, d);
    if (via_portal) *via_portal = true;
    int const p = north ? partner_n[key] : partner_w[key];
    if (p < 0) return -1;
    return (d == 0 || d == 3) ? adj(p, d) : p;
}

#include "mapbook.hpp"
#include "boards.hpp"

bool prior_on = false, prior_checked = false;
int map_bit = 0;
std::vector<uint8_t> prior_fount;

PriorMap const* map_pm = nullptr;
BookMap const* book = nullptr;

int book_d(BookRegion const& g, int c) {
    int const ch = g.dist[c];
    return ch == '~' ? -1 : ch - 35 - (ch > '?' ? 1 : 0) - (ch > '\\' ? 1 : 0);
}

void apply_prior(PriorMap const& pm) {
    map_bit = pm.bit;
    map_pm = &pm;
    if (K.mapbook & pm.bit)
        for (auto const& b : BOOK) if (b.bit == pm.bit) book = &b;
    if (!(K.map_prior & pm.bit)) return;
    for (int c = 0; c < N; ++c) { edge_n[c] = uint8_t(pm.edges[2 * c] - '0'); edge_w[c] = uint8_t(pm.edges[2 * c + 1] - '0'); }
    for (auto const& pt : pm.ports) {
        bool const north = pt[2] != 0;
        (north ? portal_n : portal_w)[pt[1]] = pt[0];
        remember_portal(pt[0], pt[1], north);
    }
    if (K.pr_fount_mask & pm.bit)
        for (int c : pm.founts) { prior_fount[c] = 1; quick_seen[c] = 3; }
    prior_on = true;
}

void apply_map_knobs() {
    static bool done = false;
    if (done || !map_bit || !K.map_knobs_on) return;
    done = true;
    switch (map_bit) {
    case 16384:
        K.keep_long_len = 10;
        break;
    default: break;
    }
}

void check_prior(std::vector<unswbc::Tile> const& tiles) {
    prior_checked = true;
    int hits = 0;
    PriorMap const* hit = nullptr;
    for (auto const& pm : PRIORS) {
        if (!((K.map_prior | K.open_maps | K.detect_maps | K.mapbook) & pm.bit) || pm.w != W || pm.h != H) continue;
        bool ok = true;
        for (int i = 0; i < VS * VS && ok; ++i) {
            auto const& t = tiles[i];
            int c = cell_of(t.get_position().x, t.get_position().y);
            for (int d = 0; d < 4 && ok; ++d) {
                auto const& e = t.get_edge(DIRS[d]);
                int kind = e.get_edge_type() == unswbc::EdgeType::KELP ? 1 : e.is_portal() ? 2 : 0;
                bool north;
                int const key = edge_key(c, d, north);
                if (pm.edges[2 * key + (north ? 0 : 1)] - '0' != kind) ok = false;
            }
        }
        if (!ok) continue;
        if (!K.detect_maps) { apply_prior(pm); return; }
        ++hits;
        if (!hit) hit = &pm;
    }
    if (hits > 1) { prior_checked = false; return; }
    if (hit) apply_prior(*hit);
}

int board_rec = 0, board_cand = -1;
int board_ev[8] = {};
void board_check(std::vector<unswbc::Tile> const& tiles) {
    if (board_cand == 0) return;
    if (board_cand < 0) {
        board_cand = 0;
        for (auto const& b : BOARDS) if (b.w == W && b.h == H) board_cand |= b.bit;
    }
    int idx = 0;
    for (auto const& b : BOARDS) {
        int const bi = idx++;
        if (!(board_cand & b.bit)) continue;
        bool ok = true;
        int marks = 0;
        for (int i = 0; i < VS * VS && ok; ++i) {
            auto const& t = tiles[i];
            int c = cell_of(t.get_position().x, t.get_position().y);
            for (int d = 0; d < 4 && ok; ++d) {
                auto const& e = t.get_edge(DIRS[d]);
                int kind = e.get_edge_type() == unswbc::EdgeType::KELP ? 1 : e.is_portal() ? 2 : 0;
                bool north;
                int const key = edge_key(c, d, north);
                int const want = b.edges[2 * key + (north ? 0 : 1)] - '0';
                if (want != kind) ok = false;
                else if (want) ++marks;
            }
        }
        if (!ok) board_cand &= ~b.bit;
        else if (marks >= K.board_ev && bi < 8) ++board_ev[bi];
    }
    if (board_cand && !(board_cand & (board_cand - 1))) {
        int i = 0;
        for (auto const& b : BOARDS) { if (b.bit == board_cand && i < 8 && board_ev[i] > 0) { board_rec = board_cand; board_cand = 0; } ++i; }
    }
}
int big_bits() {
    if (W == 64 && H == 64) return board_rec == 1 ? 1 : board_rec == 2 ? 2 : 4;
    if (W == 56 && H == 40) return 8;
    if (W == 60 && H == 40) return 16;
    if (W == 48 && H == 24) return board_rec == 32 ? 32 : board_rec == 64 ? 64 : 128;
    return N >= 2048 ? 256 : 512;
}

struct Report { int len, cell, round; };
std::unordered_map<int, Report> reports;
uint64_t team_tag() { return my_team == unswbc::Team::A ? 0x2A7 : 0x1D9; }

uint8_t checksum(uint64_t body) {
    uint64_t h = body * 0x9E3779B97F4A7C15ull;
    return static_cast<uint8_t>(h >> 56);
}
uint64_t encode(int id, Report const& r) {
    uint64_t body = (team_tag() << 50) | (uint64_t(id & 0xFFF) << 38) | (uint64_t(std::min(r.len, 511)) << 29) |
                    (uint64_t(cx(r.cell) & 63) << 23) | (uint64_t(cy(r.cell) & 63) << 17) |
                    (uint64_t(r.round & 511) << 8);
    return body | checksum(body);
}
bool decode(uint64_t m, int& id, Report& r) {
    uint64_t body = m & ~uint64_t(0xFF);
    if ((m >> 50) != team_tag() || checksum(body) != (m & 0xFF)) return false;
    id = int((m >> 38) & 0xFFF);
    r.len = int((m >> 29) & 511);
    int x = int((m >> 23) & 63), y = int((m >> 17) & 63);
    if (x >= W || y >= H) return false;
    r.cell = cell_of(x, y);
    r.round = int((m >> 8) & 511);
    return true;
}
uint64_t pair_tag() { return team_tag() ^ 0x3FF; }
uint64_t pair_check(uint64_t body) { return (body * 0x9E3779B97F4A7C15ull) >> 39; }
uint64_t encode_pair(PairRec const& p) {
    uint64_t body = (pair_tag() << 50) | (uint64_t(cx(p.a) & 63) << 44) | (uint64_t(cy(p.a) & 63) << 38) |
                    (uint64_t(cx(p.b) & 63) << 32) | (uint64_t(cy(p.b) & 63) << 26) | (uint64_t(p.north) << 25);
    return body | pair_check(body);
}
bool decode_pair(uint64_t m, int& a, int& b, bool& north) {
    uint64_t body = m & ~uint64_t(0x1FFFFFF);
    if ((m >> 50) != pair_tag() || pair_check(body) != (m & 0x1FFFFFF)) return false;
    int ax = int((m >> 44) & 63), ay = int((m >> 38) & 63), bx = int((m >> 32) & 63), by = int((m >> 26) & 63);
    if (ax >= W || ay >= H || bx >= W || by >= H) return false;
    a = cell_of(ax, ay); b = cell_of(bx, by); north = (m >> 25) & 1;
    return a != b;
}
bool edge_contradicts(int key, bool north, int other_end) {
    int const beside = north ? adj(key, 0) : adj(key, 3);
    int const known = (north ? partner_n : partner_w)[key];
    if (known >= 0 && known != other_end) return true;
    return (seen_round[key] >= 0 || seen_round[beside] >= 0) && (north ? edge_n : edge_w)[key] != 2;
}
void hear_pair(int a, int b, bool north) {
    if (edge_contradicts(a, north, b) || edge_contradicts(b, north, a)) return;
    link_pair(a, b, north);
}

std::vector<uint8_t> known_n, known_w, filled_n, filled_w;
int sym_mask = 7;

int mirror_cell(int c, int k) {
    int const x = cx(c), y = cy(c);
    if (k == 0) return cell_of(W - 1 - x, y);
    if (k == 1) return cell_of(x, H - 1 - y);
    return cell_of(W - 1 - x, H - 1 - y);
}

int mirror_key(int key, bool north, int k) {
    int const x = cx(key), y = cy(key);
    if (north) return k == 0 ? cell_of(W - 1 - x, y) : k == 1 ? cell_of(x, H - y) : cell_of(W - 1 - x, H - y);
    return k == 0 ? cell_of(W - x, y) : k == 1 ? cell_of(x, H - 1 - y) : cell_of(W - x, H - 1 - y);
}

int sym_choice() {
    int conf[3] = {0, 0, 0};
    for (int o = 0; o < 2; ++o) {
        bool const north = o == 0;
        auto const& kind = north ? edge_n : edge_w;
        auto const& known = north ? known_n : known_w;
        for (int key = 0; key < N; ++key) {
            if (!known[key]) continue;
            for (int k = 0; k < 3; ++k) {
                if (!(sym_mask >> k & 1)) continue;
                int const m = mirror_key(key, north, k);
                if (!known[m]) continue;
                if (kind[m] != kind[key]) sym_mask &= ~(1 << k);
                else if (kind[key] != 0 && m != key) ++conf[k];
            }
        }
    }
    for (auto const& p : pairs) {
        auto const& pa = p.north ? partner_n : partner_w;
        for (int k = 0; k < 3; ++k) {
            if (!(sym_mask >> k & 1)) continue;
            int const ma = mirror_key(p.a, p.north, k), mb = mirror_key(p.b, p.north, k);
            if (pa[ma] >= 0 && pa[ma] != mb) sym_mask &= ~(1 << k);
            else if (pa[ma] == mb && ma != p.a && ma != p.b) conf[k] += 4;
        }
    }
    int alive = 0, only = -1;
    for (int k = 0; k < 3; ++k) if (sym_mask >> k & 1) { ++alive; only = k; }
    if (alive == 1) return only;
    if (alive == 0 || K.sym_conf <= 0) return -1;
    int best = -1, second = 0;
    for (int k = 0; k < 3; ++k) {
        if (!(sym_mask >> k & 1)) continue;
        if (best < 0 || conf[k] > conf[best]) { if (best >= 0) second = std::max(second, conf[best]); best = k; }
        else second = std::max(second, conf[k]);
    }
    return conf[best] >= K.sym_conf && conf[best] > second ? best : -1;
}

void apply_symmetry(std::vector<int> const& visible_cells) {
    int const pick = sym_choice();
    if ((K.use_symmetry & 1) && !prior_on) {
        for (int o = 0; o < 2; ++o) {
            bool const north = o == 0;
            auto& kind = north ? edge_n : edge_w;
            auto const& known = north ? known_n : known_w;
            auto& filled = north ? filled_n : filled_w;
            auto const& partner = north ? partner_n : partner_w;
            for (int key = 0; key < N; ++key) {
                if (known[key] || partner[key] >= 0 || (!filled[key] && kind[key] != 0)) { filled[key] = 0; continue; }
                int agreed = -1;
                bool ok = sym_mask != 0;
                for (int k = 0; k < 3 && ok; ++k) {
                    if (pick >= 0 ? k != pick : !(sym_mask >> k & 1)) continue;
                    int const m = mirror_key(key, north, k);
                    if (m == key || !known[m]) { ok = false; break; }
                    if (agreed < 0) agreed = kind[m];
                    else if (agreed != kind[m]) ok = false;
                }
                kind[key] = ok && agreed > 0 ? uint8_t(agreed) : 0;
                filled[key] = kind[key] != 0;
            }
        }
    }
    if (pick < 0) return;
    if (K.use_symmetry & 2) {
        size_t const n = pairs.size();
        for (size_t i = 0; i < n; ++i) {
            PairRec const p = pairs[i];
            int const ma = mirror_key(p.a, p.north, pick), mb = mirror_key(p.b, p.north, pick);
            auto const& pa = p.north ? partner_n : partner_w;
            if (ma == mb || ma == p.a || ma == p.b || pa[ma] >= 0 || pa[mb] >= 0) continue;
            if (edge_contradicts(ma, p.north, mb) || edge_contradicts(mb, p.north, ma)) continue;
            link_pair(ma, mb, p.north);
        }
    }
    if (K.use_symmetry & 4) {
        for (int c : visible_cells) {
            int const m = mirror_cell(c, pick);
            if (m == c || seen_round[m] == round_num) continue;
            spawn_at[m] = spawn_at[c];
            quick_seen[m] = quick_seen[c];
            quick_round[m] = quick_round[c];
        }
    }
}

int champ_stale = STALE;
int best_id() {
    int best = -1; Report const* br = nullptr;
    for (auto const& [id, r] : reports) {
        if (r.round < round_num - champ_stale) continue;
        if (!br || r.len > br->len || (r.len == br->len && id < best)) { best = id; br = &r; }
    }
    return best;
}

bool queen_alive() {
    auto const q = reports.find(my_queen);
    return q != reports.end() && q->second.len > 0 && q->second.round >= round_num - K.q_alive_age;
}

int champ_id() {
    if (K.q_champ && queen_alive()) {
        if (K.q_champ == 1) return my_queen;
        int longest = 0;
        for (auto const& [id, r] : reports) if (r.round >= round_num - STALE) longest = std::max(longest, r.len);
        if (reports.find(my_queen)->second.len + K.q_champ_gap >= longest) return my_queen;
    }
    return best_id();
}

constexpr int ENEMY_ID = 4095;
Report sighting{0, -1, -1000};
bool sighting_fresh() { return sighting.cell >= 0 && sighting.round >= round_num - 12; }
constexpr int FOE_QUEEN_ID = 4094;
Report q_sight{0, -1, -1000};
bool q_sight_fresh() { return q_sight.cell >= 0 && q_sight.round >= round_num - K.q_hunt_age; }

std::deque<int> history;

struct Enemy { int head, len; bool clipped; };

struct Plan {
    bool valid = false;
    bool trap = false;
    bool harvest = false;
    bool danger = false;
    double score = -1e18;
    int dir = 0;
    bool attack = false;
};

std::vector<int> dist;
std::vector<uint8_t> bpath;
double decay[256];

std::vector<int> region_mark;
int region_stamp = 0;
int plain_region(int start, int cap) {
    ++region_stamp;
    static std::vector<int> queue; queue.clear();
    region_mark[start] = region_stamp; queue.push_back(start);
    for (size_t qi = 0; qi < queue.size() && (int)queue.size() <= cap; ++qi) {
        int c = queue[qi];
        for (int d = 0; d < 4; ++d) {
            bool north;
            int const key = edge_key(c, d, north);
            if ((north ? edge_n : edge_w)[key] != 0) continue;
            int n = adj(c, d);
            if (region_mark[n] == region_stamp) continue;
            region_mark[n] = region_stamp; queue.push_back(n);
        }
    }
    return (int)queue.size();
}

int bfs_depth = 0;
bool bfs_cycle = false;
bool bfs_terrain = false;
uint8_t bfs_blind0 = 0;
int bfs(int start, int length, int cap) {
    std::fill(dist.begin(), dist.end(), INF);
    static std::vector<int> queue; queue.clear();
    dist[start] = 1; bpath[start] = bfs_blind0; queue.push_back(start);
    int count = 0, back_edges = 0;
    bfs_depth = 1;
    for (size_t qi = 0; qi < queue.size(); ++qi) {
        int c = queue[qi]; ++count;
        bfs_depth = std::max(bfs_depth, dist[c]);
        if (count >= cap) { bfs_depth = INF; break; }
        for (int d = 0; d < 4; ++d) {
            bool vp = false;
            int n = step(c, d, &vp);
            if (n < 0) continue;
            if (dist[n] != INF) {
                ++back_edges;
                if (K.blind_tie && bpath[n] && dist[n] == dist[c] + 1 && !(bpath[c] | uint8_t(vp && seen_round[n] != round_num))) bpath[n] = 0;
                continue;
            }
            int t = dist[c] + 1;
            if (occupied(n)) {
                int s = self_seg[n];
                bool ok = s >= 0 && s >= length - (t - 1);
                if (s < 0 && ff_stamp[n] == stamp && ff_free[n] <= t - 1) ok = true;
                if (s < 0 && bfs_terrain && occ_id[n] != my_id) ok = true;
                if (!ok) continue;
            }
            dist[n] = t; bpath[n] = bpath[c] | uint8_t(vp && seen_round[n] != round_num); queue.push_back(n);
        }
    }
    bfs_cycle = bfs_depth == INF || back_edges > count - 1;
    return count;
}

std::vector<int> la_mark, la_seen;
int la_id = 0, la_seen_id = 0;
long long la_nodes = 0;
bool la_abort = false;
constexpr int LA_DEAD = -100000;

bool la_has(std::vector<int> const& v, int c, size_t upto) {
    for (size_t i = 0; i < upto && i < v.size(); ++i) if (v[i] == c) return true;
    return false;
}

int la_foe(std::vector<int> const& me, std::vector<int> const& foe, int foe_len, int depth);

int la_me(std::vector<int> const& me, std::vector<int> const& foe, int foe_len, int depth) {
    if (++la_nodes > K.lookahead_budget) { la_abort = true; return 0; }
    int best = LA_DEAD;
    for (int d = 0; d < 4 && !la_abort; ++d) {
        int const n = step(me[0], d);
        if (n < 0 || la_mark[n] == la_id || n == foe[0] || la_has(foe, n, foe.size()) || la_has(me, n, me.size() - 1)) continue;
        std::vector<int> me2;
        me2.reserve(me.size());
        me2.push_back(n);
        for (size_t i = 0; i + 1 < me.size(); ++i) me2.push_back(me[i]);
        best = std::max(best, la_foe(me2, foe, foe_len, depth));
        if (best > LA_DEAD && depth <= 1) break;
    }
    return best;
}

int la_foe(std::vector<int> const& me, std::vector<int> const& foe, int foe_len, int depth) {
    if (++la_nodes > K.lookahead_budget) { la_abort = true; return 0; }
    int const reach = std::max(1, max_steps(foe_len));
    ++la_seen_id;
    std::vector<std::array<int, 3>> q{{foe[0], -1, 0}};
    la_seen[foe[0]] = la_seen_id;
    int worst = INF;
    for (size_t qi = 0; qi < q.size() && !la_abort; ++qi) {
        int const c = q[qi][0], k = q[qi][2];
        if (k >= reach) continue;
        for (int d = 0; d < 4; ++d) {
            int const n = step(c, d);
            if (n < 0 || la_seen[n] == la_seen_id) continue;
            if (n == me[0]) return LA_DEAD;
            if (la_mark[n] == la_id || la_has(me, n, me.size()) || la_has(foe, n, foe.size())) continue;
            la_seen[n] = la_seen_id;
            q.push_back({n, int(qi), k + 1});
        }
    }
    if (q.size() == 1) return int(me.size());
    for (size_t qi = 1; qi < q.size() && !la_abort; ++qi) {
        int const len_after = foe_len - std::max(0, q[qi][2] - free_steps(foe_len));
        if (len_after < 1) continue;
        int v;
        if (depth <= 1) v = int(me.size()) - len_after;
        else {
            std::vector<int> foe2;
            for (int j = int(qi); j > 0; j = q[j][1]) foe2.push_back(q[j][0]);
            for (int c : foe) foe2.push_back(c);
            v = la_me(me, foe2, len_after, depth - 1);
        }
        worst = std::min(worst, v);
        if (worst == LA_DEAD) break;
    }
    return worst == INF ? int(me.size()) : worst;
}

struct Rng {
    uint64_t s;
    uint64_t next() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
} rng{88172645463325252ull};

int waypoint = -1, waypoint_set = -1000;
int q_nest = -1;
int start_units = -1;
std::vector<int> nest_d;
void nest_bfs() {
    std::fill(nest_d.begin(), nest_d.end(), INF);
    static std::vector<int> queue; queue.clear();
    nest_d[q_nest] = 0; queue.push_back(q_nest);
    for (size_t qi = 0; qi < queue.size(); ++qi) {
        int const c = queue[qi];
        for (int d = 0; d < 4; ++d) {
            int const n = step(c, d);
            if (n < 0 || nest_d[n] != INF) continue;
            nest_d[n] = nest_d[c] + 1; queue.push_back(n);
        }
    }
}
bool was_champion = false;
int turns_alive = 0;
int shout_until = -1;
std::unordered_map<int, int> foe_seen, pal_seen;

void turn(unswbc::Controller& ct) {
    ++stamp; ++turns_alive;
    round_num = unswbc::game->get_round_num();
    int const L = ct.get_length();
    auto const& tiles = ct.get_tiles();
    int const head = cell_of(ct.get_position().x, ct.get_position().y);
    bool const am_queen = my_id < 2;
    bool const q_on = ct.get_unit_count() >= K.q_on_units && N >= K.q_min_n;
    if (round_num == 0 && start_units < 0) start_units = ct.get_unit_count();
    bool const qa = am_queen && q_on && (K.q_min_start <= 0 || start_units >= K.q_min_start);
    bool const qs = qa && K.q_safe > 0;
    bool const qn = qa && K.q_no_ram;
    bool const qm = am_queen && round_num >= K.q_split_until;
    int const qk = am_queen ? K.q_keep : 0;
    int const big_k = L - std::max(std::max(2, qk), qa ? K.q_esc_keep : 0);
    bool const qhide = qa && K.q_hide > 0;
    if (am_queen && K.q_hide > 0 && q_nest < 0) q_nest = head;
    if (!prior_checked && (K.map_prior || K.open_maps || K.detect_maps || K.mapbook)) check_prior(tiles);
    if (K.map_knobs_on && !map_bit) map_bit = (W == 63 && H == 27) ? 16384 : (W == 48 && H == 24) ? 32768 : (W == 54 && H == 18) ? 65536 : 0;
    apply_map_knobs();
    int feed_start = (N >= 2048) ? K.feed_start_big : K.feed_start_small;
    if (K.pf_feed_start > 0 && (map_bit & K.pf_maps)) feed_start = K.pf_feed_start;
    if (K.sl_feed_start > 0 && W == 63 && H == 27) feed_start = K.sl_feed_start;
    if (K.tr_feed_start > 0 && W == 48 && H == 24) feed_start = K.tr_feed_start;
    if (K.sc_feed_start > 0 && W == 60 && H == 40) feed_start = K.sc_feed_start;
    if (K.au_feed_start > 0 && W == 54 && H == 18) feed_start = K.au_feed_start;
    if (K.is_feed_start > 0 && W == 56 && H == 40) feed_start = K.is_feed_start;
    if (K.board_on) {
        board_check(tiles);
        int const bb = big_bits();
        if (K.mz_feed_start > 0 && bb == 32) feed_start = K.mz_feed_start;
        if (K.au64_feed_start > 0 && bb == 1) feed_start = K.au64_feed_start;
        if (K.un64_feed_start > 0 && bb == 2) feed_start = K.un64_feed_start;
        if (K.board_log) ct.output_log("B", bb, board_cand);
    }
    bool feed_phase = round_num >= feed_start;
    bool split_turn = false;
    double const blind_land = prior_on && K.pr_blind_land >= 0 ? K.pr_blind_land : K.blind_land;
    double const blind_route = prior_on && K.pr_blind_route >= 0 ? K.pr_blind_route : K.blind_route;

    std::unordered_map<int, int> seg_count;
    std::unordered_map<int, bool> partial;
    std::unordered_map<int, bool> clipped;
    std::vector<int> friend_heads, visible_cells;
    std::vector<Enemy> enemies;
    visible_cells.reserve(VS * VS);
    for (int i = 0; i < VS * VS; ++i) {
        auto const& t = tiles[i];
        int c = cell_of(t.get_position().x, t.get_position().y);
        visible_cells.push_back(c);
        if (i / VS == 0 || i % VS == 0 || i / VS == VS - 1 || i % VS == VS - 1) rim_stamp[c] = stamp;
        for (int d = 0; d < 4; ++d) {
            auto const& e = t.get_edge(DIRS[d]);
            uint8_t kind = e.get_edge_type() == unswbc::EdgeType::KELP ? 1 : e.is_portal() ? 2 : 0;
            int key = c; bool north = true;
            if (d == 1) { key = adj(c, 1); north = false; }
            else if (d == 2) { key = adj(c, 2); }
            else if (d == 3) { north = false; }
            (north ? edge_n : edge_w)[key] = kind;
            if (K.use_symmetry) { (north ? known_n : known_w)[key] = 1; (north ? filled_n : filled_w)[key] = 0; }
            if (kind == 2) { (north ? portal_n : portal_w)[key] = e.get_portal_id(); remember_portal(e.get_portal_id(), key, north); ptl_stamp[c] = stamp; }
        }
        pearl_seen[c] = t.has_pearl() ? round_num : -1;
        seen_round[c] = round_num;
        int pt = t.get_pearl_time();
        spawn_at[c] = pt >= 0 ? round_num + pt : -1;
        if (pt >= 0 && pt <= 1 && quick_round[c] != round_num) {
            quick_round[c] = round_num;
            if (quick_seen[c] < 255) ++quick_seen[c];
        } else if (pt > 3 && quick_seen[c] > 0 && !prior_fount[c]) {
            quick_seen[c] = 0;
        }
        if (auto const* p = t.get_dragon()) {
            occ_stamp[c] = stamp; occ_id[c] = p->get_id(); occ_head[c] = p->is_head();
            occ_enemy[c] = p->get_team() != my_team; self_seg[c] = -1; occ_dir[c] = dir_index(p->get_dir());
            seg_count[p->get_id()]++;
            if (rim_stamp[c] == stamp || ptl_stamp[c] == stamp) partial[p->get_id()] = true;
            if (chebyshev(c, head) == R) clipped[p->get_id()] = true;
        }
    }
    if (K.reach_clip && K.reach_clip_portal)
        for (int c : visible_cells) {
            if (!occupied(c) || !occ_enemy[c] || ptl_stamp[c] != stamp || clipped.count(occ_id[c])) continue;
            bool pred = false;
            for (int d = 0; d < 4 && !pred; ++d) {
                bool en;
                int const ek = edge_key(c, d, en);
                int n = adj(c, d);
                if ((en ? edge_n : edge_w)[ek] == 0 && occupied(n) && occ_id[n] == occ_id[c] && !occ_head[n] && adj(n, occ_dir[n]) == c) pred = true;
            }
            if (!pred) clipped[occ_id[c]] = true;
        }
    for (int c : visible_cells) {
        if (!occupied(c) || !occ_head[c] || occ_id[c] == my_id) continue;
        if (occ_enemy[c]) enemies.push_back({c, seg_count[occ_id[c]], clipped.count(occ_id[c]) > 0});
        else friend_heads.push_back(c);
    }
    int q_target = -1;
    for (auto const& e : enemies) if (occ_id[e.head] < 2) q_target = e.head;
    bool const qh = K.q_hunt_len > 0 && !am_queen && L <= K.q_hunt_len;
    if (qhide) nest_bfs();
    auto nest_far = [&](int c) { return qhide && nest_d[c] > K.q_hide; };

    if (!K.history_dedupe || history.empty() || history.front() != head) history.push_front(head);
    while ((int)history.size() > L) history.pop_back();
    {
        std::vector<int> chain{head};
        int cur = head;
        while ((int)chain.size() < L) {
            int nxt = -1;
            for (int d = 0; d < 4 && nxt < 0; ++d) {
                int n = adj(cur, d);
                if (!occupied(n) || occ_id[n] != my_id || occ_head[n]) continue;
                if (K.chain_plain) {
                    bool en;
                    int const ek = edge_key(cur, d, en);
                    if ((en ? edge_n : edge_w)[ek] != 0) continue;
                }
                if (std::find(chain.begin(), chain.end(), n) != chain.end()) continue;
                auto const* t = ct.get_tile(unswbc::Position(cx(n), cy(n)));
                if (!t || !t->get_dragon()) continue;
                int fd = dir_index(t->get_dragon()->get_dir());
                if (adj(n, fd) == cur) nxt = n;
            }
            if (nxt < 0) break;
            chain.push_back(nxt); cur = nxt;
        }
        for (int s = 0; s < (int)chain.size(); ++s) self_seg[chain[s]] = s;
        if (K.history_seed && chain.size() > history.size() && std::equal(history.begin(), history.end(), chain.begin()))
            history.assign(chain.begin(), chain.end());
        int const known = K.history_young ? std::min(L, (int)history.size()) : ((int)history.size() == L ? L : 0);
        if ((int)chain.size() <= known && history[chain.size() - 1] == chain.back()) {
            for (int s = (int)chain.size(); s < known; ++s) {
                int c = history[s];
                if (!occupied(c)) { occ_stamp[c] = stamp; occ_id[c] = my_id; occ_head[c] = 0; occ_enemy[c] = 0; self_seg[c] = s; }
                else if (K.chain_plain && occ_id[c] == my_id && !occ_head[c] && self_seg[c] < 0) self_seg[c] = s;
            }
        }
        for (int c : visible_cells)
            if (occupied(c) && occ_id[c] == my_id && self_seg[c] < 0 && !occ_head[c]) self_seg[c] = -1;
    }
    int tail = -1;
    for (int c : visible_cells) if (occupied(c) && occ_id[c] == my_id && self_seg[c] == L - 1) tail = c;
    if (tail < 0 && (int)history.size() == L && self_seg[history[L - 1]] == L - 1) tail = history[L - 1];

    for (uint64_t m : ct.get_sonar_messages()) {
        int pa, pb; bool pn;
        if (decode_pair(m, pa, pb, pn)) { hear_pair(pa, pb, pn); continue; }
        int id; Report r;
        if (!decode(m, id, r) || id == my_id) continue;
        if (K.q_hunt_report && id == FOE_QUEEN_ID) {
            if (r.round > q_sight.round || (r.round == q_sight.round && q_sight.cell >= 0)) q_sight = r;
            continue;
        }
        if (id == ENEMY_ID) {
            if (!sighting_fresh() || r.round > sighting.round || (r.round == sighting.round && r.len > sighting.len)) sighting = r;
            continue;
        }
        auto it = reports.find(id);
        if (it == reports.end() || r.round >= it->second.round) reports[id] = r;
    }
    reports[my_id] = {L, head, round_num};
    if (K.use_symmetry) apply_symmetry(visible_cells);
    for (int c : friend_heads) {
        auto it = reports.find(occ_id[c]);
        if (it == reports.end()) continue;
        int const vis = seg_count[occ_id[c]];
        if (!K.sight_refresh) { it->second.cell = c; it->second.round = round_num; it->second.len = std::max(it->second.len, vis); continue; }
        it->second.cell = c;
        if (!partial.count(occ_id[c]) || vis > it->second.len) { it->second.len = vis; it->second.round = round_num; }
        else if (K.sight_partial) it->second.round = round_num;
    }
    bool const fx_on = (K.fx_relay || K.fx_stale > 0 || K.fx_tomb) && round_num >= feed_start && (big_bits() & K.fx_maps);
    if (K.tombstone) {
        for (auto& [id, r] : reports) {
            if (id == my_id || r.len == 0) continue;
            bool const far_tomb = K.fx_tomb && fx_on && chebyshev(head, r.cell) <= 1;
            if (!far_tomb && r.round < round_num - STALE) continue;
            if (!far_tomb && chebyshev(head, r.cell) + (round_num - r.round) > R - 1) continue;
            bool seen = false;
            for (int c : friend_heads) if (occ_id[c] == id) seen = true;
            if (K.tombstone_body && seg_count.count(id)) seen = true;
            if (!seen) r = {0, r.cell, round_num};
        }
    }
    for (auto it = reports.begin(); it != reports.end();) {
        if (it->second.round < round_num - 3 * STALE) it = reports.erase(it); else ++it;
    }
    if (my_id < 2) { my_queen = my_id; queen_known = true; }
    if (!queen_known) {
        for (int q = 0; q < 2 && !queen_known; ++q) if (reports.count(q)) { my_queen = q; queen_known = true; }
        for (int c : visible_cells)
            if (!queen_known && occupied(c) && occ_id[c] >= 0 && occ_id[c] < 2) { my_queen = occ_enemy[c] ? 1 - occ_id[c] : occ_id[c]; queen_known = true; }
        if (!queen_known && my_queen < 0 && round_num == 0 && turns_alive == 1) {
            bool child = false;
            for (int c : visible_cells)
                if (occupied(c) && !occ_enemy[c] && occ_id[c] >= 0 && occ_id[c] < my_id && (occ_id[c] & 1) != (my_id & 1)) child = true;
            for (auto const& [id, r] : reports) if (id < my_id && (id & 1) != (my_id & 1)) child = true;
            if (!child) my_queen = my_id & 1;
        }
    }
    foe_queen = my_queen < 0 ? -1 : 1 - my_queen;
    if (K.q_log) ct.output_log("Q", int(am_queen), my_queen, int(queen_known));
    if (K.q_champ && K.q_feed_start > 0 && queen_alive()) {
        feed_start = K.q_feed_start;
        feed_phase = round_num >= feed_start;
    }
    if (K.trap_model && (feed_phase || !K.trap_model_feed || (qa && K.q_area > 0))) {
        for (int c : visible_cells) {
            if (!occupied(c) || occ_id[c] == my_id || occ_head[c] || rim_stamp[c] == stamp || ptl_stamp[c] == stamp) continue;
            int const id = occ_id[c];
            bool pred = false;
            for (int d = 0; d < 4 && !pred; ++d) {
                int n = adj(c, d);
                if (occupied(n) && occ_id[n] == id && !occ_head[n] && adj(n, occ_dir[n]) == c) pred = true;
            }
            if (pred) continue;
            int cur = c;
            for (int j = 0; j < VS * VS; ++j) {
                ff_stamp[cur] = stamp; ff_free[cur] = j + 1 + K.model_slack + (qa ? K.q_slack : 0);
                if (occ_head[cur]) break;
                int const fd = occ_dir[cur];
                int const key = fd == 0 ? cur : fd == 2 ? adj(cur, 2) : fd == 3 ? cur : adj(cur, 1);
                if (((fd == 0 || fd == 2) ? edge_n[key] : edge_w[key]) != 0) break;
                int nxt = adj(cur, fd);
                if (!occupied(nxt) || occ_id[nxt] != id || ff_stamp[nxt] == stamp) break;
                cur = nxt;
            }
        }
    }
    champ_stale = K.fx_stale > 0 && fx_on && feed_phase ? K.fx_stale : STALE;
    bool const feed_global = feed_phase;
    int const champ = champ_id();
    if (K.q_feed_near > 0 && feed_phase && champ >= 0 && champ < 2 && champ != my_id && manhattan(head, reports[champ].cell) > K.q_feed_near) feed_phase = false;
    bool const am_champion = feed_phase && champ == my_id;
    int champ_head = -1;
    bool champ_visible = false;
    if (feed_phase && !am_champion && champ >= 0) {
        champ_head = reports[champ].cell;
        for (int c : friend_heads) if (occ_id[c] == champ) { champ_head = c; champ_visible = true; }
    }
    bool sf_out = false;
    if (K.sf_dist > 0 && (big_bits() & K.sf_maps) && feed_phase && !am_champion && champ_head >= 0 &&
        manhattan(head, champ_head) > K.sf_dist + int(K.sf_grow * (round_num - feed_start))) {
        feed_phase = false;
        sf_out = true;
    }

    for (auto const& e : enemies)
        if (e.len >= K.sighting_len && (!sighting_fresh() || e.len >= sighting.len || chebyshev(e.head, sighting.cell) <= 3))
            sighting = {e.len, e.head, round_num};
    if (K.q_hunt_report || K.q_hunt_w > 0) {
        if (q_target >= 0) q_sight = {seg_count[occ_id[q_target]], q_target, round_num};
        else if (q_sight.cell >= 0 && chebyshev(head, q_sight.cell) <= 1) {
            bool foe_q_vis = false;
            for (int c : visible_cells) if (occupied(c) && occ_enemy[c] && occ_id[c] < 2) foe_q_vis = true;
            if (!foe_q_vis) q_sight.cell = -1;
        }
    }

    int hunt = -1;
    if (!am_champion && !qn) {
        int best_len = 0;
        for (auto const& e : enemies)
            if (e.len >= std::max(5, L + 2) && e.len > best_len) { best_len = e.len; hunt = e.head; }
        if (qh && q_target >= 0) hunt = q_target;
    }
    int guard_head = -1;
    if (K.guard_radius > 0 && feed_phase && !am_champion && !qn && champ_head >= 0 && hunt < 0) {
        int best_d = K.guard_radius + 1;
        int const glen = !K.guard_fresh || !champ_visible ? reports[champ].len
                         : partial.count(champ) ? std::max(seg_count[champ], reports[champ].len) : seg_count[champ];
        bool const gok = !K.guard_fresh || ((champ_visible || reports[champ].round >= round_num - 1) && L < glen);
        for (auto const& e : enemies) {
            int const d = manhattan(e.head, champ_head);
            if (gok && e.len < glen && d < best_d && (K.guard_chase || manhattan(head, e.head) <= std::max(1, std::min(3, max_steps(L))))) {
                best_d = d; guard_head = e.head;
            }
        }
        if (K.guard_chase) hunt = guard_head;
    }
    bool const guard = guard_head >= 0;

    bool feed_blocked = false;
    if (K.feed_guard && champ_visible && !(K.q_feed_long && K.q_champ && (champ == 0 || champ == 1))) {
        int const vis = seg_count[champ];
        int const clen = partial.count(champ) ? std::max(vis, reports[champ].len) : vis;
        if (clen < L + K.feed_margin) feed_blocked = true;
        if (turns_alive <= K.feed_min_age && vis < L + K.feed_margin) feed_blocked = true;
        if (K.feed_self_frac > 0 && L >= 6 && L > K.feed_self_frac * clen) feed_blocked = true;
    }
    if (K.feed_min_units > 0 && ct.get_unit_count() < K.feed_min_units) feed_blocked = true;
    if (feed_phase && !am_champion && !qn && !(am_queen && (K.q_champ || (big_bits() & K.q_nofeed))) && champ_visible && !feed_blocked && hunt < 0 && !guard && round_num <= K.feed_last_round &&
        chebyshev(head, champ_head) <= 2) {
        if (K.crowd_reach > 0) bfs(champ_head, 0, N);
        int near = 0;
        for (int c : visible_cells)
            if (pearl_seen[c] == round_num && chebyshev(c, champ_head) <= 3 && (K.crowd_reach <= 0 || dist[c] - 1 <= K.crowd_reach)) ++near;
        bool reachable = true;
        if (K.feed_reach > 0 && near < K.crowded_pearls) {
            if (K.crowd_reach <= 0) bfs(champ_head, 0, N);
            reachable = false;
            for (int s = 0; s < (int)history.size() && !reachable; s += 2) {
                int const c = history[s];
                if (occupied(c) && occ_id[c] == my_id && self_seg[c] == s && dist[c] - 1 <= K.feed_reach) reachable = true;
            }
            for (int c : visible_cells)
                if (!reachable && occupied(c) && occ_id[c] == my_id && self_seg[c] >= 0 && self_seg[c] % 2 == 0 && dist[c] - 1 <= K.feed_reach) reachable = true;
        }
        if (near < K.crowded_pearls && reachable) {
            ct.set_indicator_string("feed");
            return;
        }
    }

    bool open_end = false;
    for (auto const& [id, ends] : portals)
        for (auto const& e : ends) if ((e.north ? partner_n : partner_w)[e.cell] < 0) open_end = true;
    bool champ_lost = false;
    if (K.portal_feed && K.portal_explore > 0 && open_end && feed_phase && !am_champion && champ_head >= 0 && !champ_visible) {
        bfs(head, L, N);
        champ_lost = true;
        for (int d = 0; d < 4; ++d) if (dist[adj(champ_head, d)] < INF) champ_lost = false;
    }
    bool starve = false;
    if (K.portal_starve > 0 && open_end && !feed_phase && !am_champion) {
        plain_region(head, N);
        int hidden = 0;
        for (int c : visible_cells)
            if (region_mark[c] != region_stamp && !occupied(c) && (pearl_seen[c] == round_num || quick_seen[c] >= 3)) ++hidden;
        starve = hidden >= K.portal_starve;
    }
    bool const portal_base = K.portal_explore > 0 && open_end && !am_champion && L <= K.portal_max_len && (!feed_phase || champ_lost) &&
                             (!K.portal_need_tail || tail >= 0);
    auto gate_std = [&]() {
        return K.portal_region <= 0 || feed_phase || starve || (K.portal_big_n > 0 && N >= K.portal_big_n) ||
               plain_region(head, K.portal_region) <= K.portal_region;
    };
    bool opening = round_num < K.open_rounds && round_num >= K.open_from && (map_bit & K.open_maps) &&
                   (int)portals.size() <= K.open_max_ids;
    bool gate = portal_base && gate_std();
    if (opening && K.open_closed_only && (portal_base ? gate : gate_std())) opening = false;
    bool const portal_ok = portal_base && (gate || opening);

    auto threat = [&](int c, bool grown) { return threat_at[c] != stamp ? INF : grown ? threat_le[c] : threat_lt[c]; };
    int const rcap = K.sprint_reach_cap > 0 ? K.sprint_reach_cap : K.reach_cap;
    if (K.reach_cap > 0 || qs) {
        static std::vector<int> rq;
        for (auto const& e : enemies) {
            if (e.len > L && !qs) continue;
            bool const shorter = e.len < L || qs;
            int pearl = 0;
            for (int d = 0; d < 4; ++d) {
                int n = step(e.head, d);
                if (n >= 0 && !occupied(n) && pearl_seen[n] == round_num) pearl = 1;
            }
            int const r = std::max(1, std::min((K.reach_clip && (e.clipped || e.len < 2) ? rcap : (qs ? true_steps(e.len) : max_steps(e.len))) + pearl, rcap));
            ++reach_id;
            reach_mark[e.head] = reach_id; reach_dist[e.head] = 0;
            rq.clear(); rq.push_back(e.head);
            for (size_t qi = 0; qi < rq.size(); ++qi) {
                int c = rq[qi];
                if (reach_dist[c] > r + (K.reach_champ_far > 0 ? 1 : 0)) continue;
                for (int d = 0; d < 4; ++d) {
                    int n = step(c, d);
                    if (n < 0 || reach_mark[n] == reach_id) continue;
                    reach_mark[n] = reach_id; reach_dist[n] = reach_dist[c] + 1;
                    int const sl = reach_dist[n] - r;
                    if (threat_at[n] != stamp) { threat_at[n] = stamp; threat_lt[n] = INF; threat_le[n] = INF; }
                    threat_le[n] = std::min(threat_le[n], sl);
                    if (shorter) threat_lt[n] = std::min(threat_lt[n], sl);
                    if (qs && sl <= 0) {
                        if (qd_at[n] != stamp) { qd_at[n] = stamp; qd[n] = INF; }
                        qd[n] = std::min(qd[n], reach_dist[n]);
                    }
                    if (!occupied(n) || (qs && self_seg[n] == L - 1)) rq.push_back(n);
                }
            }
        }
    }
    bool const qterr = qa && K.q_terr > 0 && (!enemies.empty() || (K.q_terr_mates && !friend_heads.empty()));
    if (qterr) {
        static std::vector<int> rq;
        std::vector<std::pair<int, int>> srcs;
        for (auto const& e : enemies) srcs.push_back({e.head, std::max(1, std::min((K.reach_clip && (e.clipped || e.len < 2) ? rcap : true_steps(e.len)), rcap))});
        if (K.q_terr_mates) for (int f : friend_heads) srcs.push_back({f, 1});
        for (auto const& [src, r] : srcs) {
            ++reach_id;
            reach_mark[src] = reach_id; reach_dist[src] = 0;
            rq.clear(); rq.push_back(src);
            for (size_t qi = 0; qi < rq.size(); ++qi) {
                int const c = rq[qi];
                if (reach_dist[c] >= r + 2 * R + 2) continue;
                for (int d = 0; d < 4; ++d) {
                    int const n = step(c, d);
                    if (n < 0 || reach_mark[n] == reach_id) continue;
                    reach_mark[n] = reach_id; reach_dist[n] = reach_dist[c] + 1;
                    int const tt = std::max(1, reach_dist[n] - r + 1);
                    if (qt_at[n] != stamp) { qt_at[n] = stamp; qt[n] = INF; }
                    qt[n] = std::min(qt[n], tt);
                    if (!occupied(n) || self_seg[n] == L - 1) rq.push_back(n);
                }
            }
        }
    }

    bool const locked = K.champ_lock && !feed_phase && round_num >= K.champ_lock_round && champ == my_id;
    struct Target { int cell; double value; int not_before; bool champ = false; };
    std::vector<Target> targets;
    auto pearl_value = [&](int c) -> double {
        if (K.reach_cap > 0 && (am_champion || qs || L >= K.reach_pearl_len) && threat(c, true) <= 1) return 0;
        if (feed_phase && !am_champion) {
            if (champ_head >= 0 && chebyshev(c, champ_head) <= 4) return 0;
            return (L % 2 == 0) ? 0.5 : 0.1;
        }
        double v = 1.0;
        int mine = manhattan(head, c);
        for (int f : friend_heads) if (manhattan(f, c) < mine) { v = 0.35; break; }
        return locked ? v * K.champ_pearl_mult : v;
    };
    for (int c = 0; c < N; ++c) {
        if (nest_far(c)) continue;
        if (pearl_seen[c] >= 0 && pearl_seen[c] >= round_num - PEARL_MEMORY) {
            double v = pearl_value(c);
            if (v > 0) targets.push_back({c, v, 0});
        } else if (spawn_at[c] > round_num && spawn_at[c] <= round_num + 12 && !occupied(c)) {
            double v = 0.6 * pearl_value(c);
            if (v > 0) targets.push_back({c, v, spawn_at[c] - round_num + K.spawn_lead});
        }
    }
    if (K.fountain_value > 0) {
        for (int c = 0; c < N; ++c) {
            if (quick_seen[c] < 3 || occupied(c) || pearl_seen[c] == round_num || nest_far(c)) continue;
            double v = K.fountain_value * pearl_value(c);
            if (v > 0) targets.push_back({c, v, 1});
        }
    }
    if (hunt >= 0) {
        for (int d = 0; d < 4; ++d) { int n = step(hunt, d); if (n >= 0) targets.push_back({n, 3.0, 0}); }
    }
    if (K.remote_hunt && !am_champion && hunt < 0 && sighting_fresh() && round_num >= K.hunt_start &&
        manhattan(head, sighting.cell) <= K.hunt_radius &&
        (champ_head < 0 || manhattan(head, sighting.cell) < manhattan(head, champ_head))) {
        for (int d = 0; d < 4; ++d) targets.push_back({adj(sighting.cell, d), 2.8, 0});
    }
    if (feed_phase && !am_champion && champ_head >= 0 && !feed_blocked && !(qhide && nest_far(champ_head))) {
        for (int d = 0; d < 4; ++d) { int n = adj(champ_head, d); targets.push_back({n, 2.5, 0, true}); }
        for (int d = 0; d < 4; ++d) { int n = adj(adj(champ_head, d), d); targets.push_back({n, 2.5, 0, true}); }
    }
    if (!am_champion || targets.empty()) {
        for (int c = 0; c < N; ++c) {
            if (nest_far(c)) continue;
            if (seen_round[c] < 0) targets.push_back({c, K.explore_value, 0});
            else if (seen_round[c] < round_num - 80) targets.push_back({c, 0.5 * K.explore_value, 0});
        }
    }
    if (opening && K.open_entry > 0 && !am_champion && L >= K.open_min_len && (!K.portal_need_tail || tail >= 0)) {
        for (auto const& [id, ends] : portals)
            for (auto const& e : ends) {
                int const far = (e.north ? partner_n : partner_w)[e.cell];
                if (far >= 0 && seen_round[far] >= 0 && seen_round[e.north ? adj(far, 0) : adj(far, 3)] >= 0) continue;
                int const beside = e.north ? adj(e.cell, 0) : adj(e.cell, 3);
                if (!occupied(e.cell)) targets.push_back({e.cell, K.open_entry, 0});
                if (!occupied(beside)) targets.push_back({beside, K.open_entry, 0});
            }
    }
    if (portal_ok && K.portal_entry > 0) {
        for (auto const& [id, ends] : portals)
            for (auto const& e : ends) {
                if ((e.north ? partner_n : partner_w)[e.cell] >= 0) continue;
                int const beside = e.north ? adj(e.cell, 0) : adj(e.cell, 3);
                if (!occupied(e.cell)) targets.push_back({e.cell, K.portal_entry, 0});
                if (!occupied(beside)) targets.push_back({beside, K.portal_entry, 0});
            }
    }
    if (waypoint < 0 || round_num - waypoint_set > 40 || chebyshev(head, waypoint) <= 2 || nest_far(waypoint)) {
        waypoint = int(rng.next() % uint64_t(N)); waypoint_set = round_num;
        for (int k = 0; k < 30 && nest_far(waypoint); ++k) waypoint = int(rng.next() % uint64_t(N));
        if (nest_far(waypoint)) waypoint = q_nest;
    }
    targets.push_back({waypoint, 0.1, 0});

    int const units = ct.get_unit_count();
    int const need = am_champion ? std::max(12, std::min(2 * L, 120)) : std::max(6, std::min(L + 4, 30));
    int const cap = std::max(std::max(need * 2, 60), qa ? K.q_area : 0);
    int edge = int(friend_heads.size()) + 1 - int(enemies.size());
    if (K.ram_gate && K.eq_window > 0) {
        for (auto const& e : enemies) foe_seen[occ_id[e.head]] = round_num;
        for (int f : friend_heads) pal_seen[occ_id[f]] = round_num;
        int foes = 0, pals = 1;
        for (auto const& [id, r] : foe_seen) if (r >= round_num - K.eq_window) ++foes;
        for (auto const& [id, r] : pal_seen) if (r >= round_num - K.eq_window) ++pals;
        edge = pals - foes;
    }
    auto ram_ok = [&](int elen, int cell) {
        if (qn) return false;
        if (!K.ram_gate) return elen >= L || cell == hunt || cell == guard_head;
        if (units < K.ram_min_units) return false;
        if (cell == hunt || cell == guard_head || elen > L) return units >= K.ram_long_units;
        if (elen < L) return false;
        if (units >= unswbc::game->get_unit_limit() - K.eq_free_gap || (K.eq_feed && feed_phase)) return true;
        if (round_num < K.eq_until && (!K.eq_maps || (map_bit & K.eq_maps))) return units >= K.eq_min_early && edge >= K.eq_local_early;
        return units >= K.eq_min_units && edge >= K.eq_local;
    };
    Plan best;
    Plan fallback;
    Plan declined;
    int const facing = dir_index(ct.get_dir());
    std::vector<double> areas(4, 0);
    int q_cell = -1;
    double q_pull = 0;
    if (qh && K.q_hunt_w > 0 && !am_champion && q_sight_fresh() && manhattan(head, q_sight.cell) <= K.hunt_radius) {
        q_cell = q_sight.cell;
        q_pull = K.q_hunt_w * decay[std::min(round_num - q_sight.round + 1, 255)];
    }
    auto is_trap = [&](int area, int eff_len) {
        bool const roomy = K.cycle_test ? (bfs_cycle && area >= 2 * eff_len + 4) : area >= std::max(2 * eff_len, 16);
        int horizon = std::max(20, eff_len + 4);
        if (K.horizon_cap) horizon = std::min(horizon, unswbc::Constants::MAX_ROUNDS - round_num + K.horizon_slack);
        return bfs_depth < horizon && !roomy;
    };
    BookRegion const* pull = nullptr;
    if (book && (K.mapbook & map_bit) && round_num < K.book_rounds && !feed_phase && !am_champion && L >= K.book_min_len) {
        bool safe = true;
        for (auto const& e : enemies) if (manhattan(head, e.head) <= std::max(1, max_steps(e.len)) + 1) safe = false;
        double best_sc = 0;
        for (auto const& g : book->regions) {
            if (!safe) break;
            int const dh = book_d(g, head);
            if (dh <= 2) continue;
            int crowd = 0;
            for (auto const& [id, r] : reports) {
                if (id == my_id || r.len == 0 || r.round < round_num - 2) continue;
                int const dr = book_d(g, r.cell);
                if (dr >= 0 && dr <= 3) ++crowd;
            }
            if (crowd >= K.book_region_cap) continue;
            double const sc = g.rate / (dh + 8.0);
            if (sc > best_sc) { best_sc = sc; pull = &g; }
        }
    }
    if (K.portal_reserve > 0) {
        ++rsv_id;
        for (auto const& p : pairs) {
            auto const& pa = p.north ? partner_n : partner_w;
            if (pa[p.a] != p.b) continue;
            for (int end = 0; end < 2; ++end) {
                int const key = end ? p.b : p.a;
                for (int s = 0; s < 2; ++s) {
                    int const src = s == 0 ? key : (p.north ? adj(key, 0) : adj(key, 3));
                    int const d = s == 0 ? (p.north ? 0 : 3) : (p.north ? 2 : 1);
                    if (src == head) continue;
                    bool near = false;
                    for (int f : friend_heads) if (manhattan(f, src) <= 1) near = true;
                    for (auto const& [id, r] : reports)
                        if (!near && id != my_id && r.len > 0 && r.round >= round_num - 1 && manhattan(r.cell, src) <= 1) near = true;
                    if (!near) continue;
                    int const land = step(src, d);
                    if (land < 0) continue;
                    rsv_mark[land] = rsv_id;
                    int const beyond = step(land, d);
                    if (beyond >= 0) rsv_mark[beyond] = rsv_id;
                }
            }
        }
    }
    if (K.tube_farm) {
        ++tube_id;
        auto open_seen = [&](int c, int d) {
            bool en;
            int const ek = edge_key(c, d, en);
            int const n = adj(c, d);
            return (en ? edge_n : edge_w)[ek] == 0 && seen_round[n] >= 0 ? n : -1;
        };
        auto known_walls = [&](int c) {
            int open = 0;
            for (int d = 0; d < 4; ++d) {
                bool en;
                int const ek = edge_key(c, d, en);
                uint8_t const k = (en ? edge_n : edge_w)[ek];
                if (k == 0) ++open;
                else if (k != 1) return -1;
            }
            return open;
        };
        static std::vector<int> tube;
        for (int c = 0; c < N; ++c) {
            if (seen_round[c] < 0 || known_walls(c) != 1) continue;
            tube.clear();
            tube.push_back(c);
            int prev = -1, cur = c, mouth = -1;
            auto rich = [&](int q) { return quick_seen[q] >= 2 || (pearl_seen[q] >= 0 && pearl_seen[q] >= round_num - 10); };
            bool fount = rich(c);
            while (true) {
                int nxt = -1, cnt = 0;
                for (int d = 0; d < 4; ++d) { int n = open_seen(cur, d); if (n >= 0 && n != prev) { nxt = n; ++cnt; } }
                if (cnt != 1) break;
                if (known_walls(nxt) != 2) { mouth = nxt; break; }
                prev = cur; cur = nxt;
                tube.push_back(cur);
                fount = fount || rich(cur);
            }
            if (tube.size() < 2 || mouth < 0 || !fount) continue;
            int claim = INF;
            for (auto const& [id, r] : reports) {
                if (r.len == 0 || r.round < round_num - 2) continue;
                bool in = manhattan(r.cell, mouth) <= 1;
                for (int q : tube) if (r.cell == q) in = true;
                if (in) claim = std::min(claim, id);
            }
            bool const mine = claim == INF || claim == my_id;
            bool const can_escape = L >= 4 && ct.get_unit_count() < unswbc::game->get_unit_limit();
            if (mine && can_escape) continue;
            for (int q : tube) tube_mark[q] = tube_id;
        }
    }
    std::array<int, 4> la_val;
    la_val.fill(INF);
    bool la_on = false, la_safe = false;
    if (K.lookahead && turns_alive > 1 && !enemies.empty()) {
        std::vector<int> me;
        for (int s = 0; s < (int)history.size() && s < L; ++s) me.push_back(history[s]);
        if (me.empty() || me[0] != head) me.insert(me.begin(), head);
        la_nodes = 0;
        la_abort = false;
        for (auto const& e : enemies) {
            if (la_abort || !((K.lookahead == 1 && manhattan(head, e.head) <= max_steps(e.len) + 1) || (am_champion && feed_phase))) continue;
            la_on = true;
            ++la_id;
            int const fid = occ_id[e.head];
            std::vector<int> foe{e.head};
            for (int c : visible_cells) {
                if (!occupied(c) || occ_id[c] == my_id) continue;
                if (occ_id[c] == fid) { if (c != e.head) foe.push_back(c); }
                else la_mark[c] = la_id;
            }
            for (int d = 0; d < 4 && !la_abort; ++d) {
                int const n = step(head, d);
                int v = LA_DEAD;
                if (n >= 0 && la_mark[n] != la_id && n != e.head && !la_has(foe, n, foe.size()) && !la_has(me, n, me.size() - 1)) {
                    std::vector<int> me2{n};
                    for (size_t i = 0; i + 1 < me.size(); ++i) me2.push_back(me[i]);
                    v = la_foe(me2, foe, e.len, std::max(1, K.lookahead_depth));
                }
                la_val[d] = std::min(la_val[d], v);
            }
        }
        if (la_abort) la_on = false;
        for (int d = 0; d < 4 && la_on; ++d) if (la_val[d] > LA_DEAD) la_safe = true;
    }
    std::vector<int> portal_dirs;
    for (int d = 0; d < 4; ++d) {
        if (K.no_reverse && d == (facing + 2) % 4) continue;
        bool via_portal = false;
        int t = step(head, d, &via_portal);
        if (t < 0) {
            bool kelp = false;
            {
                int key = d == 0 ? head : d == 2 ? adj(head, 2) : d == 3 ? head : adj(head, 1);
                kelp = ((d == 0 || d == 2) ? edge_n[key] : edge_w[key]) == 1;
            }
            if (!kelp && !fallback.valid) { fallback.valid = true; fallback.dir = d; fallback.score = -1e9; }
            if (!kelp && via_portal && portal_ok) portal_dirs.push_back(d);
            continue;
        }
        Plan p; p.dir = d;
        if (occupied(t)) {
            bool enemy_head = occ_head[t] && occ_enemy[t];
            if (!enemy_head || am_champion || qn) continue;
            int elen = seg_count[occ_id[t]];
            if (!ram_ok(elen, t)) {
                if (K.ram_gate && elen >= L && !declined.valid) { declined = p; declined.valid = true; declined.attack = true; declined.trap = true; }
                continue;
            }
            p.valid = true; p.attack = true; p.score = 500 + 10 * elen;
            if (p.score > best.score) best = p;
            continue;
        }
        int const eff_len = L + (pearl_seen[t] == round_num ? 1 : 0);
        bfs_blind0 = uint8_t(via_portal && seen_round[t] != round_num);
        int area = bfs(t, eff_len, cap);
        bfs_blind0 = 0;
        areas[d] = area;
        double s = 0;
        bool danger = false;
        int const depth = bfs_depth;
        bool const trap = is_trap(area, eff_len);
        bool harvest = false;
        if (K.pocket_harvest && trap && !am_champion && !qm && !qn && !(qa && K.q_no_pocket) && !feed_phase && ct.get_unit_count() < unswbc::game->get_unit_limit()) {
            int food = 0;
            bool clear = true;
            for (int q = 0; q < N; ++q) {
                if (dist[q] >= INF) continue;
                if (pearl_seen[q] == round_num || quick_seen[q] >= 3) ++food;
                if (K.harvest_clear && clear)
                    for (int e = 0; e < 4; ++e) { int n = step(q, e); if (n >= 0 && occupied(n) && occ_id[n] != my_id) clear = false; }
            }
            harvest = clear && (!K.harvest_tube || area == depth) && food >= K.harvest_pearls && L + food >= 4 &&
                      (!K.harvest_depth_check || L + food - 1 >= depth);
            for (auto const& e : enemies) if (manhattan(t, e.head) <= K.harvest_enemy_dist) harvest = false;
        }
        if (harvest) s -= K.harvest_cost;
        else if (trap) s -= 50000 + 100.0 * (20 - std::min(depth, 20)) + 50.0 * std::max(0, 16 - area);
        else if (area < need) s -= (am_champion ? 40.0 : 8.0) * (need - area);
        if (qa && K.q_area > 0 && area < K.q_area) s -= K.q_area_w * (K.q_area - area);
        for (auto const& e : enemies) {
            int md = manhattan(t, e.head);
            if (md == 1) s -= am_champion ? 5000 : (e.len >= L ? (ram_ok(e.len, e.head) ? 1 : K.eq_avoid) : 6);
            else if (md == 2 && am_champion) s -= 150;
            bool touch = md == 1;
            if (K.danger_step) {
                touch = false;
                for (int f = 0; f < 4 && !touch; ++f) touch = step(e.head, f) == t;
            }
            if (touch) danger = true;
            if (K.reach_cap > 0 && !am_champion && e.len < eff_len && units < K.reach_adj_units && !(qh && e.head == q_target))
                for (int f = 0; f < 4; ++f) if (step(e.head, f) == t) { s -= K.reach_adj + K.reach_adj_len * L; break; }
            if (qs)
                for (int f = 0; f < 4; ++f) if (step(e.head, f) == t) { s -= K.q_adj; break; }
        }
        if (qs && qd_at[t] == stamp) s -= K.q_safe * 2.0 / std::max(1, qd[t]);
        if (qhide && nest_d[t] > K.q_hide) s -= K.q_hide_w * double(std::min(nest_d[t], 1000) - K.q_hide);
        if (qa && K.q_exit > 0) {
            int safe_exits = 0;
            for (int e = 0; e < 4; ++e) {
                int const n = step(t, e);
                if (n < 0 || n == head) continue;
                if (occupied(n) && !(occ_id[n] == my_id && self_seg[n] >= L - 1)) continue;
                bool contested = false;
                for (int f = 0; f < 4 && !contested; ++f) {
                    int const m = step(n, f);
                    if (m >= 0 && m != t && occupied(m) && occ_head[m] && occ_id[m] != my_id) contested = true;
                }
                if (!contested) ++safe_exits;
            }
            if (safe_exits <= 1) s -= K.q_exit * double(2 - safe_exits);
        }
        if (qa && K.q_away > 0)
            for (auto const& e : enemies) {
                int const md = manhattan(t, e.head);
                if (md <= 4) s -= K.q_away * double((5 - md) * (5 - md));
            }
        if (qterr) {
            int terr = 0;
            for (int c : visible_cells)
                if (dist[c] < INF && (qt_at[c] != stamp || dist[c] < qt[c])) ++terr;
            if (terr < K.q_terr) s -= K.q_terr_w * double(K.q_terr - terr);
        }
        if (qa && K.q_tube > 0) {
            int open = 0;
            for (int e = 0; e < 4; ++e) if (step(t, e) >= 0) ++open;
            if (open <= 2) s -= K.q_tube;
        }
        if (K.reach_cap > 0) {
            int const sl = threat(t, eff_len > L);
            bool const big = am_champion || L >= K.reach_long_len;
            if (big && sl <= 0) { danger = danger || K.hold_danger >= 2; s -= am_champion ? K.reach_champ : K.reach_long * L; }
            else if (big && sl == 1) s -= am_champion ? K.reach_champ_edge : K.reach_long_edge;
            else if (am_champion && sl == 2) s -= K.reach_champ_far;
            if (big && sl <= 1 && (am_champion ? K.reach_corner : K.reach_corner_long) > 0) {
                int esc = -INF;
                for (int f = 0; f < 4; ++f) {
                    int n = step(t, f);
                    if (n < 0 || n == head || occupied(n)) continue;
                    esc = std::max(esc, threat(n, eff_len > L));
                }
                if (esc <= 1) s -= am_champion ? K.reach_corner : K.reach_corner_long * L;
            }
        }
        for (int f : friend_heads) {
            int md = manhattan(t, f);
            bool is_champ = feed_phase && occ_id[f] == champ;
            if (md <= 1) s -= is_champ ? 800 : (am_champion ? 200 : 12);
            if (qa && K.q_mate_adj > 0 && md <= 2) s -= md <= 1 ? K.q_mate_adj : K.q_mate_adj / 4;
            if (K.q_box > 0 && q_on && occ_id[f] < 2 && md == 1) {
                int qfree = 0;
                for (int e = 0; e < 4; ++e) { int const n = step(f, e); if (n >= 0 && n != t && !occupied(n)) ++qfree; }
                if (qfree <= 1) s -= K.q_box;
            }
            if (K.q_room > 0 && q_on && occ_id[f] < 2 && md <= K.q_room_r) s -= md <= 1 ? K.q_room : K.q_room / md / md;
            else if (md == 2 && am_champion) s -= 20;
        }
        if (via_portal && seen_round[t] != round_num && opening && K.open_blind >= 0 && !am_champion) {
            s -= K.open_blind;
        } else if (via_portal && seen_round[t] != round_num) {
            s -= am_champion ? K.champ_blind_land : blind_land;
            if (K.young_blind_land > 0 && (int)history.size() < L) s -= K.young_blind_land * double(L - (int)history.size()) / L;
            if ((am_champion ? K.champ_blind_land : blind_land) > 0)
                for (auto const& [id, r] : reports)
                    if (id != my_id && r.round >= round_num - 1 && manhattan(r.cell, t) <= 1)
                        s -= (feed_phase && id == champ) ? 800 : (am_champion ? 200 : (prior_on && K.pr_land_friend >= 0 ? K.pr_land_friend : 12));
            if (prior_on && K.pr_explore > 0 && seen_round[t] < 0 && !am_champion && (!feed_phase || champ_lost)) s += K.pr_explore;
        }
        if (qa && K.q_blind > 0 && via_portal && seen_round[t] != round_num) s -= K.q_blind;
        if (K.q_land > 0 && !am_queen && via_portal && seen_round[t] != round_num) {
            auto const q = reports.find(my_queen);
            if (q != reports.end() && q->second.len > 0 && q->second.round >= round_num - 3 && manhattan(q->second.cell, t) <= 3 + round_num - q->second.round) s -= K.q_land;
        }
        if (K.tube_farm && tube_mark[t] == tube_id && tube_mark[head] != tube_id) s -= 3000;
        if (pull) {
            int const a = book_d(*pull, head), b = book_d(*pull, t);
            if (a >= 0 && b >= 0) s += K.book_w * double(a - b);
        }
        if (K.portal_reserve > 0 && !via_portal && rsv_mark[t] == rsv_id) s -= K.portal_reserve;
        if (K.portal_turns > 0 && via_portal) {
            bool pn;
            int const key = edge_key(head, d, pn);
            int const far = (pn ? partner_n : partner_w)[key];
            if (far >= 0 && (round_num + (key < far ? 0 : 1)) % K.portal_turns != 0) s -= 1000;
        }
        if (am_champion && K.champ_portal_cell > 0) {
            for (int e = 0; e < 4; ++e) {
                bool en;
                int const ek = edge_key(t, e, en);
                if ((en ? edge_n : edge_w)[ek] == 2) { s -= K.champ_portal_cell; break; }
            }
        }
        double tv = 0;
        for (auto const& g : targets) {
            int dd = dist[g.cell];
            if (dd >= INF) continue;
            if (g.cell == t) dd = 1;
            int eta = std::max(dd, g.not_before);
            double v = g.value * 100.0 * decay[std::min(eta, 255)];
            if (blind_route < 1 && bpath[g.cell] && !(K.blind_feed_exempt && g.champ)) v *= blind_route;
            tv = std::max(tv, v);
        }
        s += tv;
        if (!am_champion && !feed_phase) {
            for (int c : visible_cells)
                if (occupied(c) && !occ_enemy[c] && occ_id[c] != my_id && chebyshev(c, t) <= 1) s -= 3;
        }
        if (K.exit_penalty > 0 && !trap) {
            int exits = 0, contested = 0;
            for (int e = 0; e < 4; ++e) {
                int n = step(t, e);
                if (n < 0 || n == head || occupied(n)) continue;
                ++exits;
                for (int f = 0; f < 4; ++f) {
                    int m = step(n, f);
                    if (m >= 0 && m != t && occupied(m) && occ_head[m] && occ_id[m] != my_id) { ++contested; break; }
                }
            }
            if (exits <= 1) {
                bool calm = contested == 0;
                if (calm && K.calm_zero && exits == 0) calm = false;
                if (calm && K.calm_radius > 0)
                    for (auto const& e : enemies) if (manhattan(t, e.head) <= K.calm_radius) calm = false;
                s -= K.exit_penalty * (calm ? K.exit_calm : 1 + contested);
            }
        }
        if (K.spawn_block > 0 && spawn_at[t] > round_num && spawn_at[t] - round_num <= eff_len && pearl_seen[t] != round_num)
            s -= K.spawn_block;
        if (round_num < K.ctr_until && K.ctr_bonus != 0 && !am_champion && (!K.ctr_maps || (map_bit & K.ctr_maps))) {
            int const mid = cell_of(W / 2, H / 2);
            s += K.ctr_bonus * double(manhattan(head, mid) - manhattan(t, mid));
        }
        if (round_num < K.cup_until && K.cup_bonus != 0 && !am_champion && map_pm && !map_pm->founts.empty() && (map_bit & K.cup_maps)) {
            int d0 = INF, d1 = INF;
            for (int f : map_pm->founts) { d0 = std::min(d0, manhattan(head, f)); d1 = std::min(d1, manhattan(t, f)); }
            s += K.cup_bonus * double(d0 - d1);
        }
        if (la_on && la_safe) {
            if (la_val[d] <= LA_DEAD) s -= 20000;
            else s += 2.0 * la_val[d];
        }
        if (q_cell >= 0) s += q_pull * double(manhattan(head, q_cell) - manhattan(t, q_cell));
        if (d == facing) s += 1.0;
        s += double(rng.next() % 100) / 1000.0;
        p.valid = true; p.score = s; p.trap = trap; p.harvest = harvest; p.danger = danger;
        if (p.score > best.score) best = p;
    }
    for (int d : portal_dirs) {
        Plan p; p.dir = d; p.valid = true;
        p.score = (opening ? std::max(K.portal_explore, K.open_portal) : K.portal_explore) + (d == facing ? 1.0 : 0.0) + double(rng.next() % 100) / 1000.0;
        if (p.score > best.score) best = p;
    }
    auto tail_exit = [&]() {
        for (int d = 0; d < 4; ++d) {
            int n = step(tail, d);
            if (n < 0 || occupied(n)) continue;
            int room = bfs(n, 0, 60);
            if (bfs_depth >= 20 || (bfs_cycle && room >= 12)) return true;
        }
        return false;
    };
    auto delaying = [&](Plan const& b) {
        return K.pocket_delay && !qm && !qn && !(qa && K.q_no_pocket) && (K.delay_in_feed || !feed_phase) && b.valid && b.trap && !b.attack &&
               pearl_seen[step(head, b.dir)] == round_num && tail >= 0 && tail_exit();
    };
    auto tail_ok = [&](Plan const& b) {
        return tail < 0 ? !(K.split_need_tail && feed_phase && !(K.hold_danger > 0 && K.hold_danger_tail && b.trap && b.danger)) : tail_exit();
    };
    auto q_size = [&]() {
        int lo = std::max(2, qk), hi = L - 2;
        if (!best.valid || best.attack || lo >= hi) return lo;
        int const t = step(head, best.dir);
        if (t < 0) return lo;
        int const extra = pearl_seen[t] == round_num ? 1 : 0;
        auto fits = [&](int ql) { return !is_trap(bfs(t, ql + extra, cap), ql + extra); };
        if (!fits(lo)) return lo;
        while (lo < hi) {
            int const mid = (lo + hi + 1) / 2;
            if (fits(mid)) lo = mid; else hi = mid - 1;
        }
        return lo;
    };
    if (declined.valid && !best.attack &&
        ((!best.valid && !fallback.valid) ||
         (K.ram_trap && units >= K.ram_min_units && best.valid && best.trap && !best.harvest &&
          !(K.escape_split && L >= 4 && ct.can_split(big_k) && (!K.ram_escape_full || delaying(best) || tail_ok(best))))))
        best = declined;

    auto note_split = [&](int k) {
        if (K.split_report) reports[my_id].len = L - k;
        if (K.split_shout > 0) shout_until = turns_alive + K.split_shout - 1;
    };
    bool split_hold = best.valid && !(best.attack && best.trap) && !(K.hold_danger > 0 && best.trap && best.danger) && (feed_phase || !K.split_guard_feed) && (L >= K.split_guard_len || (K.split_guard_champ && am_champion));
    if (split_hold && best.trap && K.split_guard_mode == 1) {
        bool open = false;
        bfs_terrain = true;
        for (int d = 0; d < 4 && !open; ++d) {
            int t = step(head, d);
            if (t < 0 || occupied(t)) continue;
            int const eff_len = L + (pearl_seen[t] == round_num ? 1 : 0);
            int area = bfs(t, eff_len, cap);
            if (!is_trap(area, eff_len)) open = true;
        }
        bfs_terrain = false;
        if (!open) split_hold = false;
    }
    bool const delay_escape = delaying(best);
    if (K.q_release > 1 && q_on && !am_queen && L >= 5 && best.valid && !best.attack && !best.trap) {
        int qhd = -1;
        for (int f : friend_heads) if (occ_id[f] < 2) qhd = f;
        int const maxm = std::min((L + 3) / 4, K.q_release);
        int freec = 0, need_m = INF;
        for (int d = 0; d < 4 && qhd >= 0; ++d) {
            int const n = step(qhd, d);
            if (n < 0) continue;
            if (!occupied(n)) ++freec;
            else if (occ_id[n] == my_id) need_m = std::min(need_m, self_seg[n] >= 1 ? L - self_seg[n] : maxm);
        }
        if (qhd >= 0 && freec == 0 && need_m >= 2 && need_m <= maxm) {
            auto near_foe = [&](int c) {
                for (auto const& e : enemies)
                    for (int f = 0; f < 4; ++f) if (step(e.head, f) == c) return true;
                return false;
            };
            std::vector<int> path{step(head, best.dir)};
            std::vector<Direction> moves{DIRS[best.dir]};
            std::vector<std::array<int, 3>> saved;
            while ((int)path.size() < need_m) {
                int const c = path.back();
                saved.push_back({c, occ_stamp[c], self_seg[c]});
                occ_stamp[c] = stamp; occ_id[c] = my_id; self_seg[c] = 0; occ_head[c] = 0; occ_enemy[c] = 0;
                int pick = -1, pick_area = -1;
                for (int d = 0; d < 4; ++d) {
                    int const n = step(c, d);
                    if (n < 0 || n == head || occupied(n) || near_foe(n)) continue;
                    int const area = bfs(n, L, cap);
                    if (!is_trap(area, L) && area > pick_area) { pick_area = area; pick = d; }
                }
                if (pick < 0) break;
                path.push_back(step(c, pick));
                moves.push_back(DIRS[pick]);
            }
            for (auto it = saved.rbegin(); it != saved.rend(); ++it) { occ_stamp[(*it)[0]] = (*it)[1]; self_seg[(*it)[0]] = (*it)[2]; }
            if ((int)moves.size() >= 2) {
                ct.make_moves(moves);
                ct.set_indicator_string("QR");
                goto sonar;
            }
        }
    }
    if (qh && q_target >= 0 && !am_champion && units >= std::max(2, K.q_hunt_units)) {
        int const maxn = std::max(1, max_steps(L));
        std::vector<std::array<int, 4>> nodes{{head, -1, -1, 0}};
        int hit = -1, hit_dir = -1;
        for (size_t qi = 0; qi < nodes.size() && hit < 0; ++qi) {
            int const c = nodes[qi][0], k = nodes[qi][3];
            for (int d = 0; d < 4; ++d) {
                if (K.no_reverse && k == 0 && d == (facing + 2) % 4) continue;
                int const n = step(c, d);
                if (n < 0) continue;
                if (n == q_target) { hit = int(qi); hit_dir = d; break; }
                if (occupied(n) || n == head || k + 1 >= maxn) continue;
                bool seen = false;
                for (auto const& q : nodes) if (q[0] == n) { seen = true; break; }
                if (!seen) nodes.push_back({n, int(qi), d, k + 1});
            }
        }
        if (hit >= 0) {
            std::vector<Direction> moves{DIRS[hit_dir]};
            for (int q = hit; nodes[q][1] >= 0; q = nodes[q][1]) moves.push_back(DIRS[nodes[q][2]]);
            std::reverse(moves.begin(), moves.end());
            ct.make_moves(moves);
            ct.set_indicator_string("QH");
            goto sonar;
        }
    }
    if (qs && K.q_flee > 1 && free_steps(L) >= 2 && best.valid && !best.attack && step(head, best.dir) >= 0) {
        auto near_head = [&](int c) {
            for (auto const& e : enemies)
                for (int f = 0; f < 4; ++f) if (step(e.head, f) == c) return true;
            return false;
        };
        int const t1 = step(head, best.dir);
        if (best.trap || qd_at[t1] == stamp || near_head(t1)) {
            int const maxk = std::min(free_steps(L), K.q_flee);
            std::vector<int> path, dirs, flee_dirs;
            int flee_area = -1;
            auto dfs = [&](auto&& rec, int c, int k) -> void {
                for (int d = 0; d < 4; ++d) {
                    if (k == 1 && K.no_reverse && d == (facing + 2) % 4) continue;
                    int const n = step(c, d);
                    if (n < 0 || n == head || occupied(n) || std::find(path.begin(), path.end(), n) != path.end()) continue;
                    path.push_back(n); dirs.push_back(d);
                    if (k >= 2 && qd_at[n] != stamp && !near_head(n)) {
                        int grow = 0;
                        std::vector<std::array<int, 3>> saved;
                        for (size_t i = 0; i < path.size(); ++i) {
                            if (pearl_seen[path[i]] == round_num) ++grow;
                            if (i + 1 == path.size()) continue;
                            int const q = path[i];
                            saved.push_back({q, occ_stamp[q], self_seg[q]});
                            occ_stamp[q] = stamp; occ_id[q] = my_id; self_seg[q] = 0; occ_head[q] = 0; occ_enemy[q] = 0;
                        }
                        int const area = bfs(n, L + grow, cap);
                        bool const tr = is_trap(area, L + grow);
                        for (auto const& sv : saved) { occ_stamp[sv[0]] = sv[1]; self_seg[sv[0]] = sv[2]; }
                        if (!tr && area > flee_area) { flee_area = area; flee_dirs = dirs; }
                    }
                    if (k < maxk) rec(rec, n, k + 1);
                    path.pop_back(); dirs.pop_back();
                }
            };
            dfs(dfs, head, 1);
            if (!flee_dirs.empty()) {
                std::vector<Direction> moves;
                for (int d : flee_dirs) moves.push_back(DIRS[d]);
                ct.make_moves(moves);
                ct.set_indicator_string("QF");
                goto sonar;
            }
        }
    }
    if (K.sprint_ram && !am_champion && !qn && !best.attack && L >= 3 && (L <= K.sprint_max_len || guard) && !enemies.empty() &&
        ct.get_unit_count() > K.sprint_min_units) {
        int const maxn = std::min(K.sprint_steps, max_steps(L));
        int const margin = round_num < K.sm_until && (!K.sm_maps || (map_bit & K.sm_maps)) ? K.sm_early : K.sprint_margin;
        std::vector<std::array<int, 4>> nodes{{head, -1, -1, 0}};
        int best_node = -1, best_last = -1, best_elen = 0, best_steps = 0;
        for (size_t qi = 0; qi < nodes.size(); ++qi) {
            int const c = nodes[qi][0], k = nodes[qi][3];
            for (int d = 0; d < 4; ++d) {
                if (K.no_reverse && k == 0 && d == (facing + 2) % 4) continue;
                int n = step(c, d);
                if (n < 0) continue;
                if (occupied(n)) {
                    if (k < 1 || !occ_head[n] || !occ_enemy[n]) continue;
                    int const elen = seg_count[occ_id[n]];
                    int const worth = (guard && n == guard_head) ? INF : (elen >= L + margin && L <= K.sprint_max_len) ? elen : 0;
                    if (worth > 0 && (worth > best_elen || (worth == best_elen && k + 1 < best_steps))) {
                        best_elen = worth; best_steps = k + 1; best_node = int(qi); best_last = d;
                    }
                    continue;
                }
                if (k + 1 >= maxn) continue;
                bool seen = false;
                for (auto const& q : nodes) if (q[0] == n) { seen = true; break; }
                if (!seen) nodes.push_back({n, int(qi), d, k + 1});
            }
        }
        if (best_node >= 0) {
            std::vector<Direction> moves{DIRS[best_last]};
            for (int q = best_node; nodes[q][1] >= 0; q = nodes[q][1]) moves.push_back(DIRS[nodes[q][2]]);
            std::reverse(moves.begin(), moves.end());
            ct.make_moves(moves);
            ct.set_indicator_string("sprint");
            goto sonar;
        }
    }
    if (K.tail_strike > 0 && tail >= 0 && L >= 4 && !best.attack && ct.can_split(2) && !qn && !qm && L - 2 >= qk) {
        for (auto const& e : enemies) {
            if (e.len < K.tail_strike || (K.ts_moved && occ_id[e.head] > my_id)) continue;
            bool near = false;
            for (int d = 0; d < 4 && !near; ++d) near = step(tail, d) == e.head;
            if (!near) continue;
            ct.do_split(2);
            note_split(2);
            ct.set_indicator_string("strike");
            split_turn = true;
            goto sonar;
        }
    }
    if (K.shield_len > 0 && K.reach_cap > 0 && L >= K.shield_len && best.valid && !best.attack && !qn && !qm &&
        (tail >= 0 || (K.shield_champ && am_champion && feed_phase && (int)history.size() == L)) && ct.can_split(big_k)) {
        int const shield_cell = tail >= 0 ? tail : history[L - 1];
        int const bt = step(head, best.dir);
        bool boxed = bt >= 0 && threat(bt, pearl_seen[bt] == round_num) <= 0;
        if (boxed && K.shield_all) {
            for (int d = 0; d < 4; ++d) {
                int const n = step(head, d);
                if (n >= 0 && !occupied(n) && threat(n, pearl_seen[n] == round_num) > 0) boxed = false;
            }
        }
        if (boxed && round_num >= K.shield_last) {
            bool late = false;
            for (auto const& e : enemies)
                if (e.len <= L && occ_id[e.head] > my_id && manhattan(head, e.head) <= rcap + 2) late = true;
            if (!late) boxed = false;
        }
        if (boxed && threat(shield_cell, true) >= K.shield_tail && (tail < 0 || tail_exit())) {
            ct.do_split(big_k);
            note_split(big_k);
            ct.set_indicator_string("shield");
            split_turn = true;
            goto sonar;
        }
    }
    if (K.escape_split && !delay_escape && (!best.valid || best.trap) && !split_hold && L >= 4 && ct.can_split(big_k) &&
        (!best.valid || tail_ok(best))) {
        int const esc_k = qm ? L - q_size() : big_k;
        ct.do_split(esc_k);
        note_split(esc_k);
        ct.set_indicator_string("escape");
        split_turn = true;
        goto sonar;
    }

    if (am_champion && best.valid && !best.attack && !(K.uturn_guard && split_hold) && areas[best.dir] < need / 2 && L >= 6 && tail >= 0 &&
        ct.get_unit_count() < unswbc::game->get_unit_limit() && big_k >= 2 && !qm) {
        int tail_area = 0;
        for (int d = 0; d < 4; ++d) {
            int n = step(tail, d);
            if (n >= 0 && !occupied(n)) tail_area = std::max(tail_area, bfs(n, 0, cap));
        }
        if (tail_area > 2 * areas[best.dir] && tail_area >= need / 2) {
            ct.do_split(big_k);
            note_split(big_k);
            ct.set_indicator_string("uturn");
            return;
        }
    }

    if (!feed_phase && !locked && !(K.kb_len > 0 && L >= K.kb_len && round_num >= K.kb_from && (big_bits() & K.kb_maps) && (!K.kb_best || champ == my_id)) && !(K.keep_long_len > 0 && L >= K.keep_long_len && round_num < K.keep_until && (map_bit & K.keep_maps)) && (round_num < feed_start - 15 || (sf_out && K.sf_split)) && L >= K.split_at && ct.can_split(2) && tail >= 0 &&
        ((!qm && L - 2 >= qk) || (am_queen && units < K.q_min_units)) &&
        (K.split_reserve <= 0 || units < unswbc::game->get_unit_limit() - K.split_reserve)) {
        auto has_exit = [&](int from, int avoid) {
            for (int d = 0; d < 4; ++d) {
                int n = step(from, d);
                if (n < 0 || occupied(n) || n == avoid) continue;
                int room = bfs(n, 0, 60);
                if (room >= 16 || bfs_depth >= 20) return true;
            }
            return false;
        };
        int crowd = 0;
        for (int c : visible_cells) if (occupied(c) && !occ_enemy[c] && occ_id[c] != my_id) ++crowd;
        int tail_free = 0;
        bool const ste = K.split_tail_exits > 0 && round_num < K.ste_until && (!K.ste_maps || (map_bit & K.ste_maps));
        if (ste)
            for (int d = 0; d < 4; ++d) { int n = step(tail, d); if (n >= 0 && !occupied(n)) ++tail_free; }
        bool threatened = crowd > K.split_crowd || !has_exit(tail, -1) || !has_exit(head, -1) || (best.valid && best.trap) ||
                          (ste && tail_free < K.split_tail_exits);
        if (!threatened) {
            int shared = 0;
            for (int d = 0; d < 4; ++d) { int n = step(head, d); if (n >= 0 && !occupied(n)) ++shared; }
            if (shared == 1) {
                for (int d = 0; d < 4; ++d) {
                    int n = step(head, d);
                    if (n >= 0 && !occupied(n) && manhattan(n, tail) <= 1) threatened = true;
                }
            }
        }
        for (auto const& e : enemies) if (manhattan(head, e.head) <= 1) threatened = true;
        if (!threatened && !(best.valid && best.attack)) {
            ct.do_split(2);
            note_split(2);
            ct.set_indicator_string("split");
            split_turn = true;
            goto sonar;
        }
    }

    if (K.ce_steps > 0 && am_champion && (big_bits() & K.ce_maps) && best.valid && !best.attack && !best.trap && L >= K.ce_min_len) {
        int const maxk = std::min(K.ce_steps, (L + 3) / 4);
        int const n1 = step(head, best.dir);
        if (maxk >= 2 && n1 >= 0) {
            std::vector<int> path{n1}, best_path;
            int best_eat = 0;
            auto safe_end = [&](int c) {
                if (threat(c, true) <= 1) return false;
                for (auto const& e : enemies) if (manhattan(e.head, c) <= 2) return false;
                return true;
            };
            auto dfs = [&](auto&& self, int c, int eaten) -> void {
                if ((int)path.size() >= 2 && eaten > best_eat && safe_end(c)) { best_eat = eaten; best_path = path; }
                if ((int)path.size() >= maxk) return;
                for (int d = 0; d < 4; ++d) {
                    int const n = step(c, d);
                    if (n < 0 || n == head || occupied(n) || pearl_seen[n] != round_num) continue;
                    if (std::find(path.begin(), path.end(), n) != path.end()) continue;
                    path.push_back(n);
                    self(self, n, eaten + 1);
                    path.pop_back();
                }
            };
            int const first = pearl_seen[n1] == round_num ? 1 : 0;
            dfs(dfs, n1, first);
            if (best_eat > first) {
                std::vector<std::array<int, 3>> saved;
                for (size_t j = 0; j + 1 < best_path.size(); ++j) {
                    int const q = best_path[j];
                    saved.push_back({q, occ_stamp[q], self_seg[q]});
                    occ_stamp[q] = stamp; occ_id[q] = my_id; self_seg[q] = 0; occ_head[q] = 0; occ_enemy[q] = 0;
                }
                int const fin = best_path.back();
                int const area = bfs(fin, L + best_eat, cap);
                bool const ok = !is_trap(area, L + best_eat) && (area >= need || bfs_depth == INF);
                for (auto const& sv : saved) { occ_stamp[sv[0]] = sv[1]; self_seg[sv[0]] = sv[2]; }
                if (ok) {
                    std::vector<Direction> mv{DIRS[best.dir]};
                    int c = n1;
                    for (size_t j = 1; j < best_path.size(); ++j)
                        for (int d = 0; d < 4; ++d) if (step(c, d) == best_path[j]) { mv.push_back(DIRS[d]); c = best_path[j]; break; }
                    if (mv.size() == best_path.size()) {
                        ct.make_moves(mv);
                        ct.set_indicator_string("CE");
                        goto sonar;
                    }
                }
            }
        }
    }
    if (K.pearl_sprint > 0 && round_num >= K.pearl_sprint && best.valid && !best.attack && !best.trap && L >= 3) {
        int const n1 = step(head, best.dir);
        if (n1 >= 0 && pearl_seen[n1] == round_num) {
            for (int d = 0; d < 4; ++d) {
                int const n2 = step(n1, d);
                if (n2 < 0 || n2 == head || occupied(n2) || pearl_seen[n2] != round_num || threat(n2, true) <= 0) continue;
                bool contested = false;
                for (auto const& e : enemies) if (manhattan(e.head, n2) <= K.ps_contest) contested = true;
                if (!contested || is_trap(bfs(n2, L + 1, cap), L + 1)) continue;
                ct.make_moves(std::vector<Direction>{DIRS[best.dir], DIRS[d]});
                ct.set_indicator_string("PS");
                goto sonar;
            }
        }
    }
    if (qn && !best.valid && !fallback.valid && ct.can_split(2)) {
        ct.do_split(2);
        note_split(2);
        ct.set_indicator_string("QS");
        split_turn = true;
        goto sonar;
    }
    if (best.valid) {
        ct.make_move(DIRS[best.dir]);
        bool vp = false, pn = false;
        if (step(head, best.dir, &vp) >= 0 && vp) {
            int const key = edge_key(head, best.dir, pn);
            for (auto& pr : pairs) if (pr.north == pn && (pr.a == key || pr.b == key)) pr.last = round_num;
        }
    }
    else if (fallback.valid) ct.make_move(DIRS[fallback.dir]);
    else if (!K.boxed_suicide) ct.make_move(DIRS[facing]);
    ct.set_indicator_string(!best.valid ? (fallback.valid ? "XP" : "XF") : best.trap ? (best.harvest ? "HV" : delay_escape ? "D" : "T") : am_champion ? "C" : hunt >= 0 ? "H" : (feed_phase ? "F" : "W"));

sonar:
    {
        int b = champ_id();
        uint64_t mine = encode(my_id, reports[my_id]);
        uint64_t best_msg = b >= 0 ? encode(b, reports[b]) : mine;
        uint64_t enemy_msg = K.q_hunt_report && q_sight_fresh() ? encode(FOE_QUEEN_ID, q_sight) : (K.fx_relay && fx_on && feed_global) ? best_msg : sighting_fresh() ? encode(ENEMY_ID, sighting) : best_msg;
        uint64_t queen_msg = best_msg;
        if (K.q_champ) {
            auto const q = reports.find(my_queen);
            if (q != reports.end() && q->second.len > 0 && q->second.round >= round_num - STALE) queen_msg = encode(my_queen, q->second);
        }
        int gossip_dir = -1, share_dir = -1;
        uint64_t gossip_msg = 0, share_msg = 0;
        bool const shout = turns_alive <= shout_until;
        if (K.portal_gossip > 0 && !shout && !pairs.empty() && round_num % K.portal_gossip == 0) {
            gossip_dir = (round_num + 1) % 4;
            gossip_msg = encode_pair(pairs[size_t(round_num / K.portal_gossip + my_id) % pairs.size()]);
        }
        if (K.portal_share && split_turn && !pairs.empty()) {
            PairRec const* pick = &pairs[0];
            for (auto const& pr : pairs) if (pr.last > pick->last) pick = &pr;
            share_dir = (facing + 2) % 4;
            share_msg = encode_pair(*pick);
        }
        for (int d = 0; d < 4; ++d) {
            uint64_t msg = shout || d == round_num % 4 ? mine : d == (round_num + 2) % 4 ? enemy_msg : d == (round_num + 3) % 4 ? queen_msg : best_msg;
            if (d == gossip_dir) msg = gossip_msg;
            if (d == share_dir) msg = share_msg;
            ct.send_sonar(DIRS[d], msg);
        }
    }
}

}

int main() {
    auto [ct, game] = unswbc::init();
    W = game.width; H = game.height; N = W * H;
    if (N < K.q_min_n) K.q_champ = 0;
    my_id = ct.get_id(); my_team = ct.get_team();
    rng.s ^= uint64_t(my_id + 1) * 0x9E3779B97F4A7C15ull;
    for (int i = 0; i < 4; ++i) rng.next();
    edge_n.assign(N, 0); edge_w.assign(N, 0); portal_n.assign(N, -1); portal_w.assign(N, -1);
    partner_n.assign(N, -1); partner_w.assign(N, -1);
    decay[0] = 1; for (int k = 1; k < 256; ++k) decay[k] = k == 1 ? 1 : decay[k - 1] * 0.88;
    seen_round.assign(N, -1);
    prior_fount.assign(N, 0);
    known_n.assign(N, 0); known_w.assign(N, 0); filled_n.assign(N, 0); filled_w.assign(N, 0);
    pearl_seen.assign(N, -1); spawn_at.assign(N, -1); quick_seen.assign(N, 0); quick_round.assign(N, -1);
    occ_stamp.assign(N, 0); occ_id.assign(N, -1); self_seg.assign(N, -1);
    occ_head.assign(N, 0); occ_enemy.assign(N, 0); occ_dir.assign(N, 0); dist.assign(N, INF); bpath.assign(N, 0); region_mark.assign(N, 0);
    ff_stamp.assign(N, 0); ff_free.assign(N, 0); rim_stamp.assign(N, 0); ptl_stamp.assign(N, 0);
    threat_at.assign(N, 0); threat_lt.assign(N, INF); threat_le.assign(N, INF); reach_mark.assign(N, 0); reach_dist.assign(N, 0); rsv_mark.assign(N, 0); la_mark.assign(N, 0); la_seen.assign(N, 0); tube_mark.assign(N, 0);
    qd.assign(N, INF); qd_at.assign(N, 0); nest_d.assign(N, INF); qt.assign(N, INF); qt_at.assign(N, 0);

    while (unswbc::update(ct, game)) {
        turn(ct);
        unswbc::end_turn();
    }
}
