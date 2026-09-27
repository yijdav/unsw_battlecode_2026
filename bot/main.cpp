// bot: swarm-then-feed bot for UNSW Battlecode 2026.
//
// Strategy (from replays of the top ladder teams):
//   1. Swarm (round < FEED_START): every dragon splits 2 off its tail as soon as it reaches
//      length 4, spreads out and harvests pearls. Small dragons ram long enemy heads, since a
//      head-on kills both regardless of length.
//   2. Feed (round >= FEED_START): the longest dragon (agreed by sonar gossip) becomes the
//      champion and plays safe. Everyone else walks to it and suicides next to it, dropping
//      ceil(L/2) pearls for it to eat. The longest living dragon wins at round 500.

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
constexpr int STALE = 20;          // rounds a sonar report stays trusted
constexpr int PEARL_MEMORY = 40;   // rounds a remembered pearl stays a target
constexpr int INF = 1 << 20;

// Tunable knobs, kept together so they're easy to experiment with.
struct Knobs {
    int feed_start_small = 320;    // maps under 2048 tiles
    int feed_start_big = 290;
    int split_at = 4;              // split 2 off the tail once this long
    int feed_last_round = 494;     // later suicides can't be eaten in time
    int crowded_pearls = 3;        // pearls already near the champion before feeders wait
    bool escape_split = true;      // a trapped dragon splits so its tail end can walk out
    double explore_value = 0.3;    // pull towards unseen tiles
    double fountain_value = 0.7;   // pull towards known fountain tiles (0 disables)
    bool cycle_test = false;       // corridors with no loop count as traps however big
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

// ---- map memory (per dragon process; children start blank) ----
// edge_n[c]: north edge of tile c, edge_w[c]: west edge. 0 empty/unknown, 1 kelp, 2 portal.
std::vector<uint8_t> edge_n, edge_w;
std::vector<int> portal_n, portal_w;   // portal id on that edge
std::vector<int> pearl_seen;           // round a pearl was last seen here, -1 none
std::vector<int> spawn_at;             // round this tile next tries to spawn, -1 unknown/never
std::vector<int> seen_round;           // last round this tile was in view, -1 never
std::vector<uint8_t> quick_seen;       // times we've seen this tile's countdown at 0 or 1
std::vector<int> quick_round;          // last round that happened (count each round once)
struct PortalEnd { int cell; bool north; };
std::unordered_map<int, std::vector<PortalEnd>> portals;

// ---- per-turn occupancy ----
std::vector<int> occ_stamp, occ_id, self_seg;
std::vector<uint8_t> occ_head, occ_enemy;
int stamp = 0;
inline bool occupied(int c) { return occ_stamp[c] == stamp; }

void remember_portal(int id, int cell, bool north) {
    auto& ends = portals[id];
    for (auto const& e : ends) if (e.cell == cell && e.north == north) return;
    ends.push_back({cell, north});
}

// Where one step from c in direction d lands, from memory. -1 for kelp or an unknown portal.
// Portal semantics follow the Loong Game's replay-verified engine reconstruction: the partner
// edge is crossed in the same direction.
int step(int c, int d, bool* via_portal = nullptr) {
    uint8_t kind; int pid; int key; bool north;
    switch (d) {
    case 0: key = c; north = true; break;
    case 2: key = adj(c, 2); north = true; break;
    case 3: key = c; north = false; break;
    default: key = adj(c, 1); north = false; break;
    }
    kind = north ? edge_n[key] : edge_w[key];
    if (via_portal) *via_portal = false;
    if (kind == 1) return -1;
    if (kind == 0) return adj(c, d);
    pid = north ? portal_n[key] : portal_w[key];
    if (via_portal) *via_portal = true;
    auto it = portals.find(pid);
    if (it == portals.end()) return -1;
    for (auto const& e : it->second) {
        if (e.cell == key && e.north == north) continue;
        return (d == 0 || d == 3) ? adj(e.cell, d) : e.cell;
    }
    return -1;  // partner not seen yet
}

// ---- sonar gossip ----
struct Report { int len, cell, round; };
std::unordered_map<int, Report> reports;
constexpr uint64_t TAG = 0x2A7;  // 10 bits

uint8_t checksum(uint64_t body) {
    uint64_t h = body * 0x9E3779B97F4A7C15ull;
    return static_cast<uint8_t>(h >> 56);
}
uint64_t encode(int id, Report const& r) {
    uint64_t body = (TAG << 50) | (uint64_t(id & 0xFFF) << 38) | (uint64_t(std::min(r.len, 511)) << 29) |
                    (uint64_t(cx(r.cell) & 63) << 23) | (uint64_t(cy(r.cell) & 63) << 17) |
                    (uint64_t(r.round & 511) << 8);
    return body | checksum(body);
}
bool decode(uint64_t m, int& id, Report& r) {
    uint64_t body = m & ~uint64_t(0xFF);
    if ((m >> 50) != TAG || checksum(body) != (m & 0xFF)) return false;
    id = int((m >> 38) & 0xFFF);
    r.len = int((m >> 29) & 511);
    int x = int((m >> 23) & 63), y = int((m >> 17) & 63);
    if (x >= W || y >= H) return false;
    r.cell = cell_of(x, y);
    r.round = int((m >> 8) & 511);
    return true;
}
// Best = longest fresh report, ties to the lowest id.
int best_id() {
    int best = -1; Report const* br = nullptr;
    for (auto const& [id, r] : reports) {
        if (r.round < round_num - STALE) continue;
        if (!br || r.len > br->len || (r.len == br->len && id < best)) { best = id; br = &r; }
    }
    return best;
}

// ---- body tracking ----
std::deque<int> history;  // head cells, most recent first

struct Enemy { int head, len; };

struct Plan {
    bool valid = false;
    bool trap = false;
    double score = -1e18;
    int dir = 0;
    bool attack = false;
};

std::vector<int> dist;
double decay[256];  // 0.88^(k-1): value of a target k steps away

// Time-aware BFS from `start` (reached at step 1). My own segment s (0 = head) is free once
// the tail has advanced past it. Returns reachable-cell count, capped.
int bfs_depth = 0;  // deepest shortest-path distance reached by the last bfs()
bool bfs_cycle = false;  // whether the region the last bfs() explored contains a loop
int bfs(int start, int length, int cap) {
    std::fill(dist.begin(), dist.end(), INF);
    static std::vector<int> queue; queue.clear();
    dist[start] = 1; queue.push_back(start);
    int count = 0, back_edges = 0;
    bfs_depth = 1;
    for (size_t qi = 0; qi < queue.size(); ++qi) {
        int c = queue[qi]; ++count;
        bfs_depth = std::max(bfs_depth, dist[c]);
        if (count >= cap) { bfs_depth = INF; break; }
        for (int d = 0; d < 4; ++d) {
            int n = step(c, d);
            if (n < 0) continue;
            if (dist[n] != INF) { ++back_edges; continue; }
            int t = dist[c] + 1;
            if (occupied(n)) {
                int s = self_seg[n];
                if (s < 0 || s < length - (t - 1)) continue;
            }
            dist[n] = t; queue.push_back(n);
        }
    }
    // Every node but the root sees its parent once as a back edge; anything more is a loop.
    bfs_cycle = bfs_depth == INF || back_edges > count - 1;
    return count;
}

struct Rng {
    uint64_t s;
    uint64_t next() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
} rng{88172645463325252ull};

int waypoint = -1, waypoint_set = -1000;
bool was_champion = false;

void turn(unswbc::Controller& ct) {
    ++stamp;
    round_num = unswbc::game->get_round_num();
    int const L = ct.get_length();
    auto const& tiles = ct.get_tiles();
    int const head = cell_of(ct.get_position().x, ct.get_position().y);
    int const feed_start = (N >= 2048) ? K.feed_start_big : K.feed_start_small;
    bool const feed_phase = round_num >= feed_start;

    // ---- read vision into memory ----
    std::unordered_map<int, int> seg_count;
    std::vector<int> friend_heads, visible_cells;
    std::vector<Enemy> enemies;
    visible_cells.reserve(VS * VS);
    for (int i = 0; i < VS * VS; ++i) {
        auto const& t = tiles[i];
        int c = cell_of(t.get_position().x, t.get_position().y);
        visible_cells.push_back(c);
        for (int d = 0; d < 4; ++d) {
            auto const& e = t.get_edge(DIRS[d]);
            uint8_t kind = e.get_edge_type() == unswbc::EdgeType::KELP ? 1 : e.is_portal() ? 2 : 0;
            int key = c; bool north = true;
            if (d == 1) { key = adj(c, 1); north = false; }
            else if (d == 2) { key = adj(c, 2); }
            else if (d == 3) { north = false; }
            (north ? edge_n : edge_w)[key] = kind;
            if (kind == 2) { (north ? portal_n : portal_w)[key] = e.get_portal_id(); remember_portal(e.get_portal_id(), key, north); }
        }
        pearl_seen[c] = t.has_pearl() ? round_num : -1;
        seen_round[c] = round_num;
        int pt = t.get_pearl_time();
        spawn_at[c] = pt >= 0 ? round_num + pt : -1;
        // Fountains (tiles with a tiny spawn gap) keep showing a countdown of 0 or 1.
        if (pt >= 0 && pt <= 1 && quick_round[c] != round_num) {
            quick_round[c] = round_num;
            if (quick_seen[c] < 255) ++quick_seen[c];
        } else if (pt > 3 && quick_seen[c] > 0) {
            quick_seen[c] = 0;
        }
        if (auto const* p = t.get_dragon()) {
            occ_stamp[c] = stamp; occ_id[c] = p->get_id(); occ_head[c] = p->is_head();
            occ_enemy[c] = p->get_team() != my_team; self_seg[c] = -1;
            seg_count[p->get_id()]++;
        }
    }
    for (int c : visible_cells) {
        if (!occupied(c) || !occ_head[c] || occ_id[c] == my_id) continue;
        if (occ_enemy[c]) enemies.push_back({c, seg_count[occ_id[c]]});
        else friend_heads.push_back(c);
    }

    // ---- my body order: chain from head through vision, then history beyond it ----
    history.push_front(head);
    while ((int)history.size() > L) history.pop_back();
    {
        std::vector<int> chain{head};
        int cur = head;
        while ((int)chain.size() < L) {
            int nxt = -1;
            for (int d = 0; d < 4 && nxt < 0; ++d) {
                int n = adj(cur, d);  // body links never cross portals in-window reliably; adjacency is enough
                if (!occupied(n) || occ_id[n] != my_id || occ_head[n]) continue;
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
        // Extend with history for segments outside the window, if history agrees with the chain.
        if ((int)history.size() == L && history[chain.size() - 1] == chain.back()) {
            for (int s = (int)chain.size(); s < L; ++s) {
                int c = history[s];
                if (!occupied(c)) { occ_stamp[c] = stamp; occ_id[c] = my_id; occ_head[c] = 0; occ_enemy[c] = 0; self_seg[c] = s; }
            }
        }
        // Anything else of mine in view (unknown order) stays blocked forever.
        for (int c : visible_cells)
            if (occupied(c) && occ_id[c] == my_id && self_seg[c] < 0 && !occ_head[c]) self_seg[c] = -1;
    }
    int tail = -1;
    for (int c : visible_cells) if (occupied(c) && occ_id[c] == my_id && self_seg[c] == L - 1) tail = c;

    // ---- gossip in ----
    for (uint64_t m : ct.get_sonar_messages()) {
        int id; Report r;
        if (!decode(m, id, r) || id == my_id) continue;
        auto it = reports.find(id);
        if (it == reports.end() || r.round >= it->second.round) reports[id] = r;
    }
    reports[my_id] = {L, head, round_num};
    // A visible dragon's head gives an exact, fresh position for its report.
    for (int c : friend_heads) {
        auto it = reports.find(occ_id[c]);
        if (it != reports.end()) { it->second.cell = c; it->second.round = round_num; it->second.len = std::max(it->second.len, seg_count[occ_id[c]]); }
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

    // ---- roles ----
    // H hunter target: a long enemy head in view (champions never hunt).
    int hunt = -1;
    if (!am_champion) {
        int best_len = 0;
        for (auto const& e : enemies)
            if (e.len >= std::max(5, L + 2) && e.len > best_len) { best_len = e.len; hunt = e.head; }
    }

    // ---- feeder suicide ----
    if (feed_phase && !am_champion && champ_visible && hunt < 0 && round_num <= K.feed_last_round &&
        chebyshev(head, champ_head) <= 2) {
        int near = 0;
        for (int c : visible_cells) if (pearl_seen[c] == round_num && chebyshev(c, champ_head) <= 3) ++near;
        if (near < K.crowded_pearls) {
            ct.set_indicator_string("feed");
            return;  // no action = suicide; our pearls drop beside the champion
        }
    }

    // ---- targets ----
    struct Target { int cell; double value; int not_before; };
    std::vector<Target> targets;
    auto pearl_value = [&](int c) -> double {
        if (feed_phase && !am_champion) {
            if (champ_head >= 0 && chebyshev(c, champ_head) <= 4) return 0;  // leave it for the champion
            return (L % 2 == 0) ? 0.5 : 0.1;  // eating at even length returns fully when we die
        }
        double v = 1.0;
        // Don't all chase the same pearl: yield it to a closer visible friend.
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
            if (v > 0) targets.push_back({c, v, spawn_at[c] - round_num});
        }
    }
    // Fountains are worth hanging round even when empty: they refill every round or so.
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
    if (feed_phase && !am_champion && champ_head >= 0) {
        for (int d = 0; d < 4; ++d) { int n = adj(champ_head, d); targets.push_back({n, 2.5, 0}); }
        for (int d = 0; d < 4; ++d) { int n = adj(adj(champ_head, d), d); targets.push_back({n, 2.5, 0}); }
    }
    // Explore: tiles never seen, then tiles not seen for a while. (Pearls sit where we aren't.)
    if (!am_champion || targets.empty()) {
        for (int c = 0; c < N; ++c) {
            if (seen_round[c] < 0) targets.push_back({c, K.explore_value, 0});
            else if (seen_round[c] < round_num - 80) targets.push_back({c, 0.5 * K.explore_value, 0});
        }
    }
    // Fallback waypoint, redrawn on arrival or every 40 rounds.
    if (waypoint < 0 || round_num - waypoint_set > 40 || chebyshev(head, waypoint) <= 2) {
        waypoint = int(rng.next() % uint64_t(N)); waypoint_set = round_num;
    }
    targets.push_back({waypoint, 0.1, 0});

    // ---- evaluate moves ----
    int const need = am_champion ? std::max(12, std::min(2 * L, 120)) : std::max(6, std::min(L + 4, 30));
    int const cap = std::max(need * 2, 60);
    Plan best;
    Plan fallback;  // unknown portal etc.
    int const facing = dir_index(ct.get_dir());
    std::vector<double> areas(4, 0);
    for (int d = 0; d < 4; ++d) {
        bool via_portal = false;
        int t = step(head, d, &via_portal);
        if (t < 0) {
            // kelp, or a portal whose far side we haven't seen: last resort only
            bool kelp = false;
            {
                int key = d == 0 ? head : d == 2 ? adj(head, 2) : d == 3 ? head : adj(head, 1);
                kelp = ((d == 0 || d == 2) ? edge_n[key] : edge_w[key]) == 1;
            }
            if (!kelp && !fallback.valid) { fallback.valid = true; fallback.dir = d; fallback.score = -1e9; }
            continue;
        }
        Plan p; p.dir = d;
        if (occupied(t)) {
            bool enemy_head = occ_head[t] && occ_enemy[t];
            if (!enemy_head || am_champion) continue;
            int elen = seg_count[occ_id[t]];
            if (elen < L && t != hunt) continue;  // only trade even or better
            p.valid = true; p.attack = true; p.score = 500 + 10 * elen;
            if (p.score > best.score) best = p;
            continue;
        }
        // Eating holds the tail back a turn, so plan with the longer body.
        int const eff_len = L + (pearl_seen[t] == round_num ? 1 : 0);
        int area = bfs(t, eff_len, cap);
        areas[d] = area;
        double s = 0;
        // A dragon can't turn round in a corridor, so a dead end of any length is fatal. Call it
        // a trap unless there's real room or the region runs deeper than our planning horizon.
        int const depth = bfs_depth;
        bool const roomy = K.cycle_test ? (bfs_cycle && area >= 2 * eff_len + 4) : area >= std::max(2 * eff_len, 16);
        bool const trap = depth < std::max(20, eff_len + 4) && !roomy;
        if (trap) s -= 50000 + 100.0 * (20 - std::min(depth, 20)) + 50.0 * std::max(0, 16 - area);
        else if (area < need) s -= (am_champion ? 40.0 : 8.0) * (need - area);
        // threats
        for (auto const& e : enemies) {
            int md = manhattan(t, e.head);
            if (md == 1) s -= am_champion ? 5000 : (e.len >= L ? 1 : 6);
            else if (md == 2 && am_champion) s -= 150;
        }
        for (int f : friend_heads) {
            int md = manhattan(t, f);
            bool is_champ = feed_phase && occ_id[f] == champ;
            if (md <= 1) s -= is_champ ? 800 : (am_champion ? 200 : 12);
            else if (md == 2 && am_champion) s -= 20;
        }
        // targets
        double tv = 0;
        for (auto const& g : targets) {
            int dd = dist[g.cell];
            if (dd >= INF) continue;
            if (g.cell == t) dd = 1;
            int eta = std::max(dd, g.not_before);
            double v = g.value * 100.0 * decay[std::min(eta, 255)];
            tv = std::max(tv, v);
        }
        s += tv;
        // spread the swarm: friendly segments close to t
        if (!am_champion && !feed_phase) {
            for (int c : visible_cells)
                if (occupied(c) && !occ_enemy[c] && occ_id[c] != my_id && chebyshev(c, t) <= 1) s -= 3;
        }
        if (d == facing) s += 1.0;
        s += double(rng.next() % 100) / 1000.0;  // deterministic tie-break
        p.valid = true; p.score = s; p.trap = trap;
        if (p.score > best.score) best = p;
    }

    // ---- trapped: split as much as we can off the tail; the child leaves the way we came in ----
    auto tail_exit = [&]() {
        for (int d = 0; d < 4; ++d) {
            int n = step(tail, d);
            if (n < 0 || occupied(n)) continue;
            int room = bfs(n, 0, 60);
            if (bfs_depth >= 20 || (bfs_cycle && room >= 12)) return true;
        }
        return false;
    };
    if (K.escape_split && (!best.valid || best.trap) && L >= 4 && tail >= 0 && ct.can_split(L - 2) && tail_exit()) {
        ct.do_split(L - 2);
        ct.set_indicator_string("escape");
        goto sonar;
    }

    // ---- champion U-turn: if boxed in, leave 2 behind and let the long child run the other way ----
    if (am_champion && best.valid && !best.attack && areas[best.dir] < need / 2 && L >= 6 && tail >= 0 &&
        ct.get_unit_count() < unswbc::game->get_unit_limit()) {
        int tail_area = 0;
        for (int d = 0; d < 4; ++d) {
            int n = step(tail, d);
            if (n >= 0 && !occupied(n)) tail_area = std::max(tail_area, bfs(n, 0, cap));
        }
        if (tail_area > 2 * areas[best.dir] && tail_area >= need / 2) {
            ct.do_split(L - 2);
            ct.set_indicator_string("uturn");
            return;
        }
    }

    // ---- swarm split ----
    if (!feed_phase && round_num < feed_start - 15 && L >= K.split_at && ct.can_split(2) && tail >= 0) {
        // The child's head is our tail. It needs an exit that isn't a dead end.
        // Both halves need a real exit, with the whole current body still in the way: the
        // child moves off later this round and can easily plug the parent's only way out.
        auto has_exit = [&](int from, int avoid) {
            for (int d = 0; d < 4; ++d) {
                int n = step(from, d);
                if (n < 0 || occupied(n) || n == avoid) continue;
                int room = bfs(n, 0, 60);
                if (room >= 16 || bfs_depth >= 20) return true;
            }
            return false;
        };
        bool threatened = !has_exit(tail, -1) || !has_exit(head, -1) || (best.valid && best.trap);
        // A single shared exit tile means the child will sit in it.
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
            ct.set_indicator_string("split");
            goto sonar;
        }
    }

    if (best.valid) ct.make_move(DIRS[best.dir]);
    else if (fallback.valid) ct.make_move(DIRS[fallback.dir]);
    else ct.make_move(DIRS[facing]);  // nothing safe; this is death either way
    ct.set_indicator_string(am_champion ? "C" : hunt >= 0 ? "H" : (feed_phase ? "F" : "W"));

sonar:
    // ---- gossip out: best-known dragon everywhere, our own report on one rotating ray ----
    {
        int b = best_id();
        uint64_t mine = encode(my_id, reports[my_id]);
        uint64_t best_msg = b >= 0 ? encode(b, reports[b]) : mine;
        for (int d = 0; d < 4; ++d) ct.send_sonar(DIRS[d], d == round_num % 4 ? mine : best_msg);
    }
}

}  // namespace

int main() {
    auto [ct, game] = unswbc::init();
    W = game.width; H = game.height; N = W * H;
    my_id = ct.get_id(); my_team = ct.get_team();
    rng.s ^= uint64_t(my_id + 1) * 0x9E3779B97F4A7C15ull;
    for (int i = 0; i < 4; ++i) rng.next();
    edge_n.assign(N, 0); edge_w.assign(N, 0); portal_n.assign(N, -1); portal_w.assign(N, -1);
    decay[0] = 1; for (int k = 1; k < 256; ++k) decay[k] = k == 1 ? 1 : decay[k - 1] * 0.88;
    seen_round.assign(N, -1);
    pearl_seen.assign(N, -1); spawn_at.assign(N, -1); quick_seen.assign(N, 0); quick_round.assign(N, -1);
    occ_stamp.assign(N, 0); occ_id.assign(N, -1); self_seg.assign(N, -1);
    occ_head.assign(N, 0); occ_enemy.assign(N, 0); dist.assign(N, INF);

    while (unswbc::update(ct, game)) {
        turn(ct);
        unswbc::end_turn();
    }
}
