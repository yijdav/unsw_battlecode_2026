# unsw_battlecode_2026

A C++ bot for [UNSW Battlecode 2026](https://game.battlecode.au/docs/overview) (the sea-dragon Snake game). The bot is in [`bot/`](bot/main.cpp).

## Strategy

I got this from replays of the current top 5 ladder teams: 54 recent games decoded and analysed. Every one of those teams plays the same two-phase game:

1. **Swarm (rounds 0–~300).** Split 2 off the tail as soon as a dragon reaches length 4. The team fills up toward the 64-dragon cap, spreads out and harvests pearls. Small dragons ram long enemy heads: a head-on collision kills both, whatever their lengths.
2. **Feed (~300–500).** The longest dragon becomes the champion and plays safe. Every other dragon walks to it and dies next to it, dropping ⌈L/2⌉ pearls for it to eat. For the winning teams, 58–92% of their final champion's pearls came from their own dragons dying. The longest living dragon wins at round 500.

How `bot` plays it:

- **Sonar gossip.** Each dragon broadcasts a report (id, length, position, round) and relays the longest report it has heard. The swarm agrees on a champion without shared memory. Messages carry a tag and a checksum, so enemy sonar is ignored.
- **Map memory.** Each dragon remembers kelp, portals, pearls, spawn countdowns and fountain tiles (tiles that refill every round or so). It plans with a pathfinding search over the whole wrapped map, using only what it has seen itself.
- **Trap avoidance.** A dragon can't turn round in a one-wide corridor. Moves into dead ends are vetoed. Before splitting, the bot checks that both halves have an exit. A trapped dragon splits so its tail end can walk out.
- **Champion safety.** The champion never steps next to an enemy head, keeps its room, and does a U-turn split when it is boxed in.
- **Exploration.** Dragons head for tiles they've never seen, then for tiles they haven't seen in a while.

It costs about 5M of the judge's 100M CPU points per dragon per turn, including on 64×64 maps.

## Running it

```bash
unswbc run maps/ladder/default.map bot bot            # one match
unswbc run --sandbox maps/ladder/default.map bot bot    # priced like the judge
python3 tools/arena.py bot v_test --maps maps/ladder -j 8 --seeds 2   # every map, both sides
python3 tools/variant.py v_test feed_start_small=350     # copy bot with a knob changed, for A/B
unswbc submit bot -n v1 -d "swarm + feed"
```

`maps/ladder/` holds the ten maps currently used on the ladder, extracted from public replays. The tunable knobs are in the `Knobs` struct at the top of [`bot/main.cpp`](bot/main.cpp).
