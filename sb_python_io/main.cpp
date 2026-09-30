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
    int feed_start_small = 383;
    int feed_start_big = 383;
    int split_at = 4;
    int feed_last_round = 496;
    int crowded_pearls = 5;
    bool escape_split = true;
    double explore_value = 0.1882;
    double fountain_value = 0.6071;
    bool cycle_test = false;
    double exit_penalty = 8.519;
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
    int feed_min_age = 2;
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
    double portal_explore = 15;
    double portal_entry = 0.1873;
    bool portal_feed = true;
    int portal_max_len = 99;
    int portal_region = 0;
    bool portal_share = true;
    int portal_gossip = 2;
    bool portal_need_tail = true;
    double blind_land = 49.94;
    double champ_blind_land = 300;
    double champ_portal_cell = 100;
    int spawn_lead = 1;
    double spawn_block = 53.83;
    int reach_cap = 4;
    bool reach_clip = true;
    double reach_champ = 5000;
    double reach_champ_edge = 105.6;
    double reach_champ_far = 32.02;
    int reach_long_len = 5;
    double reach_long = 34.84;
    double reach_long_edge = 30;
    double reach_adj = 286.3;
    double reach_adj_len = 20;
    int reach_adj_units = 999;
    int reach_pearl_len = 8;
    double reach_corner = 2000;
    double reach_corner_long = 30;
    bool sprint_ram = true;
    int sprint_margin = -1;
    int sprint_max_len = 4;
    int sprint_steps = 3;
    int guard_radius = 5;
    bool guard_chase = false;
    int sprint_min_units = 1;
    bool pocket_delay = true;
    bool delay_in_feed = true;
    bool pocket_harvest = true;
    int harvest_pearls = 2;
    double harvest_cost = 20.71;
    int harvest_enemy_dist = 0;
    bool harvest_depth_check = true;
    bool harvest_tube = true;
    bool harvest_clear = true;
    bool ram_gate = true;
    int ram_min_units = 2;
    int ram_long_units = 2;
    int eq_min_units = 9;
    int eq_free_gap = 12;
    int eq_local = 1;
    int eq_window = 0;
    double eq_avoid = 9.691;
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
    int portal_starve = 0;
    int portal_big_n = 2048;
    int split_reserve = 0;
    bool shield_champ = false;
    int split_tail_exits = 0;
    int ram_any_len = 3;
    int ram_any_min = 2;
    bool sprint_any = true;
    int sprint_min_target = 2;
    double chase_value = 0;
    int chase_min_len = 2;
    int chase_max_len = 4;
    int chase_units = 4;
    int centre_rounds = 25;
    double centre_bonus = 15;
    int ram_any_from = 50;
} K;

int W, H, N;
int round_num;
int my_id;
unswbc::Team my_team = unswbc::Team::A;
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
std::vector<int> threat_at, threat_lt, threat_le, reach_mark, reach_dist;
int stamp = 0, reach_id = 0;
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

int best_id() {
    int best = -1; Report const* br = nullptr;
    for (auto const& [id, r] : reports) {
        if (r.round < round_num - STALE) continue;
        if (!br || r.len > br->len || (r.len == br->len && id < best)) { best = id; br = &r; }
    }
    return best;
}

constexpr int ENEMY_ID = 4095;
Report sighting{0, -1, -1000};
bool sighting_fresh() { return sighting.cell >= 0 && sighting.round >= round_num - 12; }

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

struct Rng {
    uint64_t s;
    uint64_t next() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
} rng{88172645463325252ull};

int waypoint = -1, waypoint_set = -1000;
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
    int const feed_start = (N >= 2048) ? K.feed_start_big : K.feed_start_small;
    bool const feed_phase = round_num >= feed_start;
    bool split_turn = false;

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
            if (kind == 2) { (north ? portal_n : portal_w)[key] = e.get_portal_id(); remember_portal(e.get_portal_id(), key, north); ptl_stamp[c] = stamp; }
        }
        pearl_seen[c] = t.has_pearl() ? round_num : -1;
        seen_round[c] = round_num;
        int pt = t.get_pearl_time();
        spawn_at[c] = pt >= 0 ? round_num + pt : -1;
        if (pt >= 0 && pt <= 1 && quick_round[c] != round_num) {
            quick_round[c] = round_num;
            if (quick_seen[c] < 255) ++quick_seen[c];
        } else if (pt > 3 && quick_seen[c] > 0) {
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
    if (K.trap_model && (feed_phase || !K.trap_model_feed)) {
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
                ff_stamp[cur] = stamp; ff_free[cur] = j + 1 + K.model_slack;
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
    int tail = -1;
    for (int c : visible_cells) if (occupied(c) && occ_id[c] == my_id && self_seg[c] == L - 1) tail = c;
    if (tail < 0 && (int)history.size() == L && self_seg[history[L - 1]] == L - 1) tail = history[L - 1];

    for (uint64_t m : ct.get_sonar_messages()) {
        int pa, pb; bool pn;
        if (decode_pair(m, pa, pb, pn)) { hear_pair(pa, pb, pn); continue; }
        int id; Report r;
        if (!decode(m, id, r) || id == my_id) continue;
        if (id == ENEMY_ID) {
            if (!sighting_fresh() || r.round > sighting.round || (r.round == sighting.round && r.len > sighting.len)) sighting = r;
            continue;
        }
        auto it = reports.find(id);
        if (it == reports.end() || r.round >= it->second.round) reports[id] = r;
    }
    reports[my_id] = {L, head, round_num};
    for (int c : friend_heads) {
        auto it = reports.find(occ_id[c]);
        if (it == reports.end()) continue;
        int const vis = seg_count[occ_id[c]];
        if (!K.sight_refresh) { it->second.cell = c; it->second.round = round_num; it->second.len = std::max(it->second.len, vis); continue; }
        it->second.cell = c;
        if (!partial.count(occ_id[c]) || vis > it->second.len) { it->second.len = vis; it->second.round = round_num; }
        else if (K.sight_partial) it->second.round = round_num;
    }
    if (K.tombstone) {
        for (auto& [id, r] : reports) {
            if (id == my_id || r.len == 0 || r.round < round_num - STALE) continue;
            if (chebyshev(head, r.cell) + (round_num - r.round) > R - 1) continue;
            bool seen = false;
            for (int c : friend_heads) if (occ_id[c] == id) seen = true;
            if (K.tombstone_body && seg_count.count(id)) seen = true;
            if (!seen) r = {0, r.cell, round_num};
        }
    }
    for (auto it = reports.begin(); it != reports.end();) {
        if (it->second.round < round_num - 3 * STALE) it = reports.erase(it); else ++it;
    }
    int const champ = best_id();
    bool const am_champion = feed_phase && champ == my_id;
    int champ_head = -1;
    bool champ_visible = false;
    if (feed_phase && !am_champion && champ >= 0) {
        champ_head = reports[champ].cell;
        for (int c : friend_heads) if (occ_id[c] == champ) { champ_head = c; champ_visible = true; }
    }

    for (auto const& e : enemies)
        if (e.len >= K.sighting_len && (!sighting_fresh() || e.len >= sighting.len || chebyshev(e.head, sighting.cell) <= 3))
            sighting = {e.len, e.head, round_num};

    int hunt = -1;
    if (!am_champion) {
        int best_len = 0;
        for (auto const& e : enemies)
            if (e.len >= std::max(5, L + 2) && e.len > best_len) { best_len = e.len; hunt = e.head; }
    }
    int guard_head = -1;
    if (K.guard_radius > 0 && feed_phase && !am_champion && champ_head >= 0 && hunt < 0) {
        int best_d = K.guard_radius + 1;
        int const glen = !K.guard_fresh || !champ_visible ? reports[champ].len
                         : partial.count(champ) ? std::max(seg_count[champ], reports[champ].len) : seg_count[champ];
        bool const gok = !K.guard_fresh || ((champ_visible || reports[champ].round >= round_num - 1) && L < glen);
        for (auto const& e : enemies) {
            int const d = manhattan(e.head, champ_head);
            if (gok && e.len < glen && d < best_d && (K.guard_chase || manhattan(head, e.head) <= std::max(1, std::min(3, L - 1)))) {
                best_d = d; guard_head = e.head;
            }
        }
        if (K.guard_chase) hunt = guard_head;
    }
    bool const guard = guard_head >= 0;

    bool feed_blocked = false;
    if (K.feed_guard && champ_visible) {
        int const vis = seg_count[champ];
        int const clen = partial.count(champ) ? std::max(vis, reports[champ].len) : vis;
        if (clen < L + K.feed_margin) feed_blocked = true;
        if (turns_alive <= K.feed_min_age && vis < L + K.feed_margin) feed_blocked = true;
        if (K.feed_self_frac > 0 && L >= 6 && L > K.feed_self_frac * clen) feed_blocked = true;
    }
    if (K.feed_min_units > 0 && ct.get_unit_count() < K.feed_min_units) feed_blocked = true;
    if (feed_phase && !am_champion && champ_visible && !feed_blocked && hunt < 0 && !guard && round_num <= K.feed_last_round &&
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
    bool const portal_ok = K.portal_explore > 0 && open_end && !am_champion && L <= K.portal_max_len && (!feed_phase || champ_lost) &&
                           (!K.portal_need_tail || tail >= 0) &&
                           (K.portal_region <= 0 || feed_phase || starve || (K.portal_big_n > 0 && N >= K.portal_big_n) ||
                            plain_region(head, K.portal_region) <= K.portal_region);

    auto threat = [&](int c, bool grown) { return threat_at[c] != stamp ? INF : grown ? threat_le[c] : threat_lt[c]; };
    if (K.reach_cap > 0) {
        static std::vector<int> rq;
        for (auto const& e : enemies) {
            if (e.len > L) continue;
            bool const shorter = e.len < L;
            int pearl = 0;
            for (int d = 0; d < 4; ++d) {
                int n = step(e.head, d);
                if (n >= 0 && !occupied(n) && pearl_seen[n] == round_num) pearl = 1;
            }
            int const r = std::max(1, std::min((K.reach_clip && (e.clipped || e.len < 2) ? K.reach_cap : e.len - 1) + pearl, K.reach_cap));
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
                    if (!occupied(n)) rq.push_back(n);
                }
            }
        }
    }

    int const units_now = ct.get_unit_count();
    bool const centre_map = (W == 25 && H == 25) || (W == 54 && H == 18) || (W == 63 && H == 27) || (W == 32 && H == 16);
    struct Target { int cell; double value; int not_before; bool champ = false; };
    std::vector<Target> targets;
    auto pearl_value = [&](int c) -> double {
        if (K.reach_cap > 0 && (am_champion || L >= K.reach_pearl_len) && threat(c, true) <= 1) return 0;
        if (feed_phase && !am_champion) {
            if (champ_head >= 0 && chebyshev(c, champ_head) <= 4) return 0;
            return (L % 2 == 0) ? 0.5 : 0.1;
        }
        double v = 1.0;
        int mine = manhattan(head, c);
        for (int f : friend_heads) if (manhattan(f, c) < mine) { v = 0.35; break; }
        return v;
    };
    for (int c = 0; c < N; ++c) {
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
            if (quick_seen[c] < 3 || occupied(c) || pearl_seen[c] == round_num) continue;
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
    if (feed_phase && !am_champion && champ_head >= 0 && !feed_blocked) {
        for (int d = 0; d < 4; ++d) { int n = adj(champ_head, d); targets.push_back({n, 2.5, 0, true}); }
        for (int d = 0; d < 4; ++d) { int n = adj(adj(champ_head, d), d); targets.push_back({n, 2.5, 0, true}); }
    }
    if (!am_champion || targets.empty()) {
        for (int c = 0; c < N; ++c) {
            if (seen_round[c] < 0) targets.push_back({c, K.explore_value, 0});
            else if (seen_round[c] < round_num - 80) targets.push_back({c, 0.5 * K.explore_value, 0});
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
    if (K.chase_value > 0 && !am_champion && !feed_phase && L >= K.chase_min_len && L <= K.chase_max_len && units_now >= K.chase_units) {
        for (auto const& e : enemies) {
            if (e.len < K.ram_any_min) continue;
            for (int d = 0; d < 4; ++d) { int n = step(e.head, d); if (n >= 0 && !occupied(n)) targets.push_back({n, K.chase_value, 0}); }
        }
    }
    if (waypoint < 0 || round_num - waypoint_set > 40 || chebyshev(head, waypoint) <= 2) {
        waypoint = int(rng.next() % uint64_t(N)); waypoint_set = round_num;
    }
    targets.push_back({waypoint, 0.1, 0});

    int const units = ct.get_unit_count();
    int const need = am_champion ? std::max(12, std::min(2 * L, 120)) : std::max(6, std::min(L + 4, 30));
    int const cap = std::max(need * 2, 60);
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
        if (!K.ram_gate) return elen >= L || cell == hunt || cell == guard_head;
        if (units < K.ram_min_units) return false;
        if (K.ram_any_len > 0 && round_num >= K.ram_any_from && L <= K.ram_any_len && elen >= K.ram_any_min && !am_champion) return true;
        if (cell == hunt || cell == guard_head || elen > L) return units >= K.ram_long_units;
        if (elen < L) return false;
        if (units >= unswbc::game->get_unit_limit() - K.eq_free_gap || (K.eq_feed && feed_phase)) return true;
        return units >= K.eq_min_units && edge >= K.eq_local;
    };
    Plan best;
    Plan fallback;
    Plan declined;
    int const facing = dir_index(ct.get_dir());
    std::vector<double> areas(4, 0);
    auto is_trap = [&](int area, int eff_len) {
        bool const roomy = K.cycle_test ? (bfs_cycle && area >= 2 * eff_len + 4) : area >= std::max(2 * eff_len, 16);
        int horizon = std::max(20, eff_len + 4);
        if (K.horizon_cap) horizon = std::min(horizon, unswbc::Constants::MAX_ROUNDS - round_num + K.horizon_slack);
        return bfs_depth < horizon && !roomy;
    };
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
            if (!enemy_head || am_champion) continue;
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
        if (K.pocket_harvest && trap && !am_champion && !feed_phase && ct.get_unit_count() < unswbc::game->get_unit_limit()) {
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
        for (auto const& e : enemies) {
            int md = manhattan(t, e.head);
            bool const brave = K.ram_any_len > 0 && round_num >= K.ram_any_from && L <= K.ram_any_len && e.len >= K.ram_any_min;
            if (md == 1) s -= am_champion ? 5000 : (e.len >= L ? (ram_ok(e.len, e.head) ? 1 : K.eq_avoid) : brave ? 1 : 6);
            else if (md == 2 && am_champion) s -= 150;
            bool touch = md == 1;
            if (K.danger_step) {
                touch = false;
                for (int f = 0; f < 4 && !touch; ++f) touch = step(e.head, f) == t;
            }
            if (touch) danger = true;
            if (K.reach_cap > 0 && !am_champion && !brave && e.len < eff_len && units < K.reach_adj_units)
                for (int f = 0; f < 4; ++f) if (step(e.head, f) == t) { s -= K.reach_adj + K.reach_adj_len * L; break; }
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
            else if (md == 2 && am_champion) s -= 20;
        }
        if (via_portal && seen_round[t] != round_num) {
            s -= am_champion ? K.champ_blind_land : K.blind_land;
            if (K.young_blind_land > 0 && (int)history.size() < L) s -= K.young_blind_land * double(L - (int)history.size()) / L;
            if ((am_champion ? K.champ_blind_land : K.blind_land) > 0)
                for (auto const& [id, r] : reports)
                    if (id != my_id && r.round >= round_num - 1 && manhattan(r.cell, t) <= 1)
                        s -= (feed_phase && id == champ) ? 800 : (am_champion ? 200 : 12);
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
            if (K.blind_route < 1 && bpath[g.cell] && !(K.blind_feed_exempt && g.champ)) v *= K.blind_route;
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
        if (d == facing) s += 1.0;
        if (K.centre_bonus > 0 && round_num < K.centre_rounds && !am_champion && centre_map) {
            int const mid = cell_of(W / 2, H / 2);
            s += K.centre_bonus * (manhattan(head, mid) - manhattan(t, mid));
        }
        s += double(rng.next() % 100) / 1000.0;
        p.valid = true; p.score = s; p.trap = trap; p.harvest = harvest; p.danger = danger;
        if (p.score > best.score) best = p;
    }
    for (int d : portal_dirs) {
        Plan p; p.dir = d; p.valid = true;
        p.score = K.portal_explore + (d == facing ? 1.0 : 0.0) + double(rng.next() % 100) / 1000.0;
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
        return K.pocket_delay && (K.delay_in_feed || !feed_phase) && b.valid && b.trap && !b.attack &&
               pearl_seen[step(head, b.dir)] == round_num && tail >= 0 && tail_exit();
    };
    auto tail_ok = [&](Plan const& b) {
        return tail < 0 ? !(K.split_need_tail && feed_phase && !(K.hold_danger > 0 && K.hold_danger_tail && b.trap && b.danger)) : tail_exit();
    };
    if (declined.valid && !best.attack &&
        ((!best.valid && !fallback.valid) ||
         (K.ram_trap && units >= K.ram_min_units && best.valid && best.trap && !best.harvest &&
          !(K.escape_split && L >= 4 && ct.can_split(L - 2) && (!K.ram_escape_full || delaying(best) || tail_ok(best))))))
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
    if (K.sprint_ram && !am_champion && !best.attack && L >= 3 && (L <= K.sprint_max_len || guard) && !enemies.empty() &&
        ct.get_unit_count() > K.sprint_min_units) {
        int const maxn = std::min(K.sprint_steps, L - 1);
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
                    int const worth = (guard && n == guard_head) ? INF
                                      : (L <= K.sprint_max_len && (elen >= L + K.sprint_margin || (K.sprint_any && round_num >= K.ram_any_from && L <= K.ram_any_len && elen >= K.sprint_min_target))) ? elen : 0;
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
    if (K.shield_len > 0 && K.reach_cap > 0 && L >= K.shield_len && best.valid && !best.attack &&
        (tail >= 0 || (K.shield_champ && am_champion && feed_phase && (int)history.size() == L)) && ct.can_split(L - 2)) {
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
                if (e.len <= L && occ_id[e.head] > my_id && manhattan(head, e.head) <= K.reach_cap + 2) late = true;
            if (!late) boxed = false;
        }
        if (boxed && threat(shield_cell, true) >= K.shield_tail && (tail < 0 || tail_exit())) {
            ct.do_split(L - 2);
            note_split(L - 2);
            ct.set_indicator_string("shield");
            split_turn = true;
            goto sonar;
        }
    }
    if (K.escape_split && !delay_escape && (!best.valid || best.trap) && !split_hold && L >= 4 && ct.can_split(L - 2) &&
        (!best.valid || tail_ok(best))) {
        ct.do_split(L - 2);
        note_split(L - 2);
        ct.set_indicator_string("escape");
        split_turn = true;
        goto sonar;
    }

    if (am_champion && best.valid && !best.attack && !(K.uturn_guard && split_hold) && areas[best.dir] < need / 2 && L >= 6 && tail >= 0 &&
        ct.get_unit_count() < unswbc::game->get_unit_limit()) {
        int tail_area = 0;
        for (int d = 0; d < 4; ++d) {
            int n = step(tail, d);
            if (n >= 0 && !occupied(n)) tail_area = std::max(tail_area, bfs(n, 0, cap));
        }
        if (tail_area > 2 * areas[best.dir] && tail_area >= need / 2) {
            ct.do_split(L - 2);
            note_split(L - 2);
            ct.set_indicator_string("uturn");
            return;
        }
    }

    if (!feed_phase && round_num < feed_start - 15 && L >= K.split_at && ct.can_split(2) && tail >= 0 &&
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
        if (K.split_tail_exits > 0)
            for (int d = 0; d < 4; ++d) { int n = step(tail, d); if (n >= 0 && !occupied(n)) ++tail_free; }
        bool threatened = crowd > K.split_crowd || !has_exit(tail, -1) || !has_exit(head, -1) || (best.valid && best.trap) ||
                          (K.split_tail_exits > 0 && tail_free < K.split_tail_exits);
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
        int b = best_id();
        uint64_t mine = encode(my_id, reports[my_id]);
        uint64_t best_msg = b >= 0 ? encode(b, reports[b]) : mine;
        uint64_t enemy_msg = sighting_fresh() ? encode(ENEMY_ID, sighting) : best_msg;
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
            uint64_t msg = shout || d == round_num % 4 ? mine : d == (round_num + 2) % 4 ? enemy_msg : best_msg;
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
    my_id = ct.get_id(); my_team = ct.get_team();
    rng.s ^= uint64_t(my_id + 1) * 0x9E3779B97F4A7C15ull;
    for (int i = 0; i < 4; ++i) rng.next();
    edge_n.assign(N, 0); edge_w.assign(N, 0); portal_n.assign(N, -1); portal_w.assign(N, -1);
    partner_n.assign(N, -1); partner_w.assign(N, -1);
    decay[0] = 1; for (int k = 1; k < 256; ++k) decay[k] = k == 1 ? 1 : decay[k - 1] * 0.88;
    seen_round.assign(N, -1);
    pearl_seen.assign(N, -1); spawn_at.assign(N, -1); quick_seen.assign(N, 0); quick_round.assign(N, -1);
    occ_stamp.assign(N, 0); occ_id.assign(N, -1); self_seg.assign(N, -1);
    occ_head.assign(N, 0); occ_enemy.assign(N, 0); occ_dir.assign(N, 0); dist.assign(N, INF); bpath.assign(N, 0); region_mark.assign(N, 0);
    ff_stamp.assign(N, 0); ff_free.assign(N, 0); rim_stamp.assign(N, 0); ptl_stamp.assign(N, 0);
    threat_at.assign(N, 0); threat_lt.assign(N, INF); threat_le.assign(N, INF); reach_mark.assign(N, 0); reach_dist.assign(N, 0);

    while (unswbc::update(ct, game)) {
        turn(ct);
        unswbc::end_turn();
    }
}
